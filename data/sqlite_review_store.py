"""SqliteReviewStore: SQLAlchemy/SQLite adapter for ReviewStore (imperative shell — I/O).

Contract models are stored as JSON text columns (immutable snapshots). The schema is plain
relational so it ports to Postgres/Supabase in Block 2 with no service change.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    insert,
    inspect,
    select,
)

from agent.models import ControllerInput, Draft, InvestigationRecord
from data.review_store import (
    ReviewAction,
    ReviewActionType,
    ReviewItem,
    ReviewStatus,
    ReviewStore,
)

_metadata = MetaData()

review_item = Table(
    "review_item", _metadata,
    Column("current_period", Integer, primary_key=True),  # composite PK: (current_period, flag_id)
    Column("flag_id", String, primary_key=True),
    Column("reporting_line", String, nullable=False),
    Column("status", String, nullable=False),
    Column("record_json", Text),
    Column("original_draft_json", Text),
    Column("controller_answer_json", Text),
    Column("edited_text", Text),
    Column("error", Text),
    Column("created_at", String),
    Column("updated_at", String),
)

review_action = Table(
    "review_action", _metadata,
    Column("action_id", String, primary_key=True),
    Column("flag_id", String, nullable=False),
    Column("current_period", Integer, nullable=False),
    Column("action", String, nullable=False),
    Column("actor", String, nullable=False),
    Column("ts", String, nullable=False),
    Column("from_status", String, nullable=False),
    Column("to_status", String, nullable=False),
    Column("payload_json", Text),
)


def _dump(model) -> Optional[str]:
    return json.dumps(model.model_dump(mode="json")) if model is not None else None


def _load(cls, raw: Optional[str]):
    return cls.model_validate(json.loads(raw)) if raw else None


class SqliteReviewStore(ReviewStore):
    def __init__(self, sqlite_path: Path) -> None:
        sqlite_path = Path(sqlite_path)
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{sqlite_path}")
        self._recreate_if_incompatible()
        _metadata.create_all(self.engine)

    def _recreate_if_incompatible(self) -> None:
        """Drop the review tables if an existing schema predates the (current_period, flag_id) key.

        The primary key changed, so a DB written by the old single-key schema cannot be used. The
        review DB is dev-only, git-ignored, mock-state (Constitution VIII), so a recreate is safe
        and also clears stale rows. A fresh DB (no review_item table) is left for create_all.
        """
        inspector = inspect(self.engine)
        if not inspector.has_table("review_item"):
            return
        columns = {c["name"] for c in inspector.get_columns("review_item")}
        if "current_period" not in columns:
            _metadata.drop_all(self.engine)

    def get(self, current_period: int, flag_id: str) -> Optional[ReviewItem]:
        with self.engine.connect() as conn:
            row = conn.execute(
                select(review_item).where(
                    review_item.c.current_period == current_period,
                    review_item.c.flag_id == flag_id,
                )
            ).mappings().first()
        return self._row_to_item(row) if row else None

    def upsert(self, item: ReviewItem) -> None:
        values = {
            "current_period": item.current_period,
            "flag_id": item.flag_id,
            "reporting_line": item.reporting_line,
            "status": item.status.value,
            "record_json": _dump(item.record),
            "original_draft_json": _dump(item.original_draft),
            "controller_answer_json": _dump(item.controller_answer),
            "edited_text": item.edited_text,
            "error": item.error,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        stmt = sqlite_insert(review_item).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["current_period", "flag_id"], set_=values
        )
        with self.engine.begin() as conn:
            conn.execute(stmt)

    def list_all(self, current_period: int) -> list[ReviewItem]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(review_item).where(review_item.c.current_period == current_period)
            ).mappings().all()
        return [self._row_to_item(r) for r in rows]

    def append_action(self, action: ReviewAction) -> None:
        with self.engine.begin() as conn:
            conn.execute(insert(review_action).values(
                action_id=action.action_id, flag_id=action.flag_id,
                current_period=action.current_period,
                action=action.action.value, actor=action.actor, ts=action.ts,
                from_status=action.from_status.value, to_status=action.to_status.value,
                payload_json=json.dumps(action.payload) if action.payload is not None else None,
            ))

    def actions_for(self, current_period: int, flag_id: str) -> list[ReviewAction]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(review_action).where(
                    review_action.c.current_period == current_period,
                    review_action.c.flag_id == flag_id,
                ).order_by(review_action.c.action_id)
            ).mappings().all()
        return [
            ReviewAction(
                action_id=r["action_id"], flag_id=r["flag_id"], current_period=r["current_period"],
                action=ReviewActionType(r["action"]), actor=r["actor"], ts=r["ts"],
                from_status=ReviewStatus(r["from_status"]), to_status=ReviewStatus(r["to_status"]),
                payload=json.loads(r["payload_json"]) if r["payload_json"] else None,
            )
            for r in rows
        ]

    @staticmethod
    def _row_to_item(row) -> ReviewItem:
        return ReviewItem(
            flag_id=row["flag_id"],
            current_period=row["current_period"],
            reporting_line=row["reporting_line"],
            status=ReviewStatus(row["status"]),
            record=_load(InvestigationRecord, row["record_json"]),
            original_draft=_load(Draft, row["original_draft_json"]),
            controller_answer=_load(ControllerInput, row["controller_answer_json"]),
            edited_text=row["edited_text"],
            error=row["error"],
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
        )
