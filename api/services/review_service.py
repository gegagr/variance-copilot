"""Application/service layer: orchestrates engine + agent + review store; holds the workflow.

This is the workflow brain. It applies the lifecycle state machine, runs the Block 3 agent, and
persists review state. It contains **no financial computation** — P&L/flag/commentary figures
come from the engine/agent objects verbatim (Constitution: Determinism First). It never imports
FastAPI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from config.loader import load_config
from config.schemas import EngineConfig
from data.repository import Repository
from data.review_store import (
    RESOLVED,
    ReviewAction,
    ReviewActionType,
    ReviewItem,
    ReviewStatus,
    ReviewStore,
)
from engine.flagging import flag_variances
from engine.models import FlaggedVariance, PnLResult, TimeCut
from engine.pnl import build_pnl
from engine.variance import compute_variances
from agent.audit import AuditLog
from agent.investigate import draft_from_controller, investigate as agent_investigate
from agent.models import ControllerInput
from agent.tools import GLRowSource, make_gl_tool
from api.schemas import AcceptedCommentaryItem, ReviewProgressView
from api.services.lifecycle import transition


class NotFound(Exception):
    """Unknown period or flag id."""


class ReviewService:
    def __init__(self, *, repo: Repository, gl_repo: GLRowSource, config: EngineConfig,
                 config_dir: Path, agent_settings, provider, store: ReviewStore,
                 controller_id: str = "controller") -> None:
        self.repo = repo
        self.gl_repo = gl_repo
        self.config = config
        self.config_dir = Path(config_dir)
        self.agent_settings = agent_settings
        self.provider = provider
        self.store = store
        self.controller_id = controller_id
        self.audit = AuditLog()
        self._session_period = config.settings.current_period
        self._gl_tool = make_gl_tool(gl_repo, config)
        self._action_seq = 0

    # --- read-through (no figure constructed) ---------------------------------
    def get_pnl(self, current_period: int, time_cut: TimeCut) -> PnLResult:
        cfg = self._config_for(current_period)
        return build_pnl(self.repo.get_transactions(), cfg)

    def get_flags(self, current_period: int) -> list[FlaggedVariance]:
        flags = self._flags_for(current_period)
        if current_period == self._session_period:
            self._ensure_items(flags)
        return flags

    # --- workflow actions ------------------------------------------------------
    def investigate(self, flag_id: str, *, now: str) -> ReviewItem:
        flag = self._session_flag(flag_id)
        item = self._ensure_item(flag)
        new = transition(item.status, ReviewActionType.INVESTIGATE)  # detected/drafted -> investigating
        from_status = item.status
        # Fresh run: discard prior provenance.
        item.status = new
        item.record = None
        item.original_draft = None
        item.edited_text = None
        item.updated_at = now

        record = agent_investigate(
            flag, self._session_pnl(), provider=self.provider, gl_tool=self._gl_tool,
            settings=self.agent_settings, audit=self.audit, now=now,
        )
        if record is None:  # Block 3 fail-safe: no grounded output -> back to detected, no commentary
            item.status = ReviewStatus.DETECTED
        elif record.status.value == "question":
            item.status = ReviewStatus.AWAITING_CONTROLLER
            item.record = record
        else:  # self-explanatory draft
            item.status = ReviewStatus.DRAFTED
            item.record = record
            item.original_draft = record.draft

        item.updated_at = now
        self.store.upsert(item)
        self._record_action(ReviewActionType.INVESTIGATE, flag_id, from_status, item.status, now)
        return item

    def answer(self, flag_id: str, text: str, accepted_hypothesis: bool, *, now: str) -> ReviewItem:
        item = self._require(flag_id)
        new = transition(item.status, ReviewActionType.ANSWER)  # awaiting_controller -> drafted
        flag = self._session_flag(flag_id)
        ci = ControllerInput(input_id=f"{flag_id}:answer", flag_id=flag_id, text=text,
                             accepted_hypothesis=accepted_hypothesis)
        evidence = item.record.evidence if item.record else []
        draft = draft_from_controller(
            flag, evidence, ci, provider=self.provider, settings=self.agent_settings,
            audit=self.audit, now=now,
        )
        if draft is None:  # drafting fail-safe: stay awaiting, no commentary
            return item
        from_status = item.status
        item.status = new
        item.controller_answer = ci
        item.original_draft = draft
        item.updated_at = now
        self.store.upsert(item)
        self._record_action(ReviewActionType.ANSWER, flag_id, from_status, item.status, now,
                            payload={"text": text})
        return item

    def accept(self, flag_id: str, *, now: str) -> ReviewItem:
        return self._simple_action(flag_id, ReviewActionType.ACCEPT, now)

    def dismiss(self, flag_id: str, *, now: str) -> ReviewItem:
        return self._simple_action(flag_id, ReviewActionType.DISMISS, now)

    def edit(self, flag_id: str, edited_text: str, *, now: str) -> ReviewItem:
        item = self._require(flag_id)
        new = transition(item.status, ReviewActionType.EDIT)  # drafted|accepted -> drafted
        from_status = item.status
        item.status = new
        item.edited_text = edited_text  # original_draft retained (provenance preserved)
        item.updated_at = now
        self.store.upsert(item)
        self._record_action(ReviewActionType.EDIT, flag_id, from_status, item.status, now,
                            payload={"edited_text": edited_text})
        return item

    # --- progress & assembled output ------------------------------------------
    def progress(self) -> ReviewProgressView:
        total = len(self._session_flags())
        items = self.store.list_all()
        by_status: dict[str, int] = {}
        for it in items:
            by_status[it.status.value] = by_status.get(it.status.value, 0) + 1
        resolved = sum(1 for it in items if it.status in RESOLVED)
        return ReviewProgressView(total=total, resolved=resolved, by_status=by_status)

    def accepted_commentary(self) -> list[AcceptedCommentaryItem]:
        order_of = {row.reporting_line: row.order for row in self.config.layout}
        out: list[AcceptedCommentaryItem] = []
        for it in self.store.list_all():
            if it.status is not ReviewStatus.ACCEPTED or it.original_draft is None:
                continue
            text = it.edited_text if it.edited_text is not None else it.original_draft.commentary
            out.append(AcceptedCommentaryItem(
                flag_id=it.flag_id, reporting_line=it.reporting_line,
                order=order_of.get(it.reporting_line, 10**6), text=text,
                is_edited=it.edited_text is not None, provenance=it.original_draft.provenance,
            ))
        out.sort(key=lambda x: (x.order, x.flag_id))
        return out

    def history(self, flag_id: str) -> list[ReviewAction]:
        self._require(flag_id)
        return self.store.actions_for(flag_id)

    # --- helpers ---------------------------------------------------------------
    def _config_for(self, current_period: int) -> EngineConfig:
        if current_period == self._session_period:
            return self.config
        return load_config(self.config_dir, current_period=current_period)

    def _session_pnl(self) -> PnLResult:
        return build_pnl(self.repo.get_transactions(), self.config)

    def _session_flags(self) -> list[FlaggedVariance]:
        return self._flags_for(self._session_period)

    def _flags_for(self, current_period: int) -> list[FlaggedVariance]:
        cfg = self._config_for(current_period)
        pnl = build_pnl(self.repo.get_transactions(), cfg)
        return flag_variances(compute_variances(pnl, cfg), cfg)

    def _session_flag(self, flag_id: str) -> FlaggedVariance:
        for f in self._session_flags():
            if f.flag_id == flag_id:
                return f
        raise NotFound(f"unknown flag {flag_id}")

    def _ensure_items(self, flags: list[FlaggedVariance]) -> None:
        for f in flags:
            self._ensure_item(f)

    def _ensure_item(self, flag: FlaggedVariance) -> ReviewItem:
        existing = self.store.get(flag.flag_id)
        if existing is not None:
            return existing
        item = ReviewItem(flag_id=flag.flag_id, reporting_line=flag.reporting_line,
                          status=ReviewStatus.DETECTED)
        self.store.upsert(item)
        return item

    def _require(self, flag_id: str) -> ReviewItem:
        item = self.store.get(flag_id)
        if item is None:
            raise NotFound(f"unknown flag {flag_id}")
        return item

    def _simple_action(self, flag_id: str, action: ReviewActionType, now: str) -> ReviewItem:
        item = self._require(flag_id)
        new = transition(item.status, action)
        from_status = item.status
        item.status = new
        item.updated_at = now
        self.store.upsert(item)
        self._record_action(action, flag_id, from_status, item.status, now)
        return item

    def _record_action(self, action, flag_id, from_status, to_status, now, payload=None) -> None:
        self._action_seq += 1
        action_id = f"{flag_id}|{action.value}|{now}|{self._action_seq}"
        self.store.append_action(ReviewAction(
            action_id=action_id, flag_id=flag_id, action=action,
            actor=self.controller_id, ts=now, from_status=from_status, to_status=to_status,
            payload=payload,
        ))
