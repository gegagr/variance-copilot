"""The investigation loop (provider-agnostic agent core).

Given a flag + P&L context and the injected ports, run a bounded tool-call loop: the model
calls `query_gl_detail` to gather evidence, then emits a structured Question or Draft. Every
output passes the traceability guard (with one bounded retry); provider/parse failures
fail safe (logged, no ungrounded output). Contains NO SDK/HTTP calls.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from pydantic import ValidationError

from config.agent_settings import AgentSettings
from engine.models import FlaggedVariance, PnLResult
from agent import commentary
from agent.audit import AuditLog
from agent.commentary import RenderError
from agent.guards import assert_grounded, assert_no_raw_digits
from agent.models import (
    ControllerInput,
    Draft,
    EmitPayload,
    GLEvidenceRow,
    GLQuery,
    Hypothesis,
    InvestigationRecord,
    RecordStatus,
)
from agent.tools import QUERY_GL_DETAIL_TOOL, grounded_gl_query
from agent.provider import FORCE_EMIT, LLMProvider, StructuredFinal, TextResponse, ToolCall

logger = logging.getLogger("variance_copilot.investigate")

# The CLOSED set of flag figure fields a {{fig:flag.<field>}} token may reference.
_FLAG_FIELDS = ", ".join(commentary.VALID_FLAG_FIGURE_FIELDS)

EMIT_INVESTIGATION_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "emit_investigation",
        "description": (
            "Emit the final investigation result: a question or a draft. You NEVER write a digit and "
            "NEVER compute: reference existing figures only, by token, and ONLY inside `narrative` "
            "(and `hypothesis_text`). Valid tokens — and nothing else — are: "
            f"{{{{fig:flag.<field>}}}} where <field> is one of [{_FLAG_FIELDS}] (do NOT invent a field "
            "such as 'direction'); {{fig:gl:<txn_id>.amount}} for a transaction returned by "
            "query_gl_detail; {{fig:agg:<id>}} for an aggregate you declare in `aggregates`. To show a "
            "total or count, declare an aggregate (op over row_ids) and cite it — never write "
            "arithmetic like '{{fig:a}} - {{fig:b}}' anywhere."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["status", "narrative"],
            "properties": {
                "status": {"enum": ["question", "draft"]},
                "hypothesis_text": {
                    "type": ["string", "null"],
                    "description": "Plain prose; may contain {{fig:...}} tokens. No digits, no arithmetic.",
                },
                "hypothesis_row_ids": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Transaction ids only (NOT figure tokens).",
                },
                "narrative": {
                    "type": "string",
                    "description": "The commentary/question. Every figure is a {{fig:...}} token; "
                    "no raw digits and no arithmetic between figures.",
                },
                "cited_row_ids": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Transaction ids only (NOT figure tokens).",
                },
                "aggregates": {
                    "type": "array",
                    "description": "STRUCTURED aggregates only — never a string or an arithmetic "
                    "expression. Each item computes one value the code evaluates over cited rows.",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["agg_id", "op", "row_ids"],
                        "properties": {
                            "agg_id": {"type": "string"},
                            "op": {"enum": ["sum", "count", "min", "max"]},
                            "row_ids": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
            },
        },
    },
}

GLTool = Callable[[GLQuery], "object"]


def _retry_emit_prompt(reason: str) -> str:
    """Re-prompt fed back on a rejected emit, naming the specific problem and the exact rules."""
    return (
        f"Your emit_investigation call was rejected — {reason}. Call emit_investigation again, fixed. "
        "Rules: put {{fig:...}} tokens ONLY in `narrative` (and `hypothesis_text`); reference existing "
        "figures only — never invent a field and never write arithmetic. Valid tokens: "
        f"{{{{fig:flag.<field>}}}} where <field> is one of [{_FLAG_FIELDS}]; {{fig:gl:<txn_id>.amount}} "
        "for a returned transaction; {{fig:agg:<id>}} for an aggregate you list in `aggregates` as "
        "{agg_id, op (sum|count|min|max), row_ids:[...]}."
    )


def _emit_error_detail(exc: ValidationError) -> str:
    """A concise, field-named summary of why an emit payload failed validation."""
    parts = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err["loc"]) or "(root)"
        parts.append(f"field '{loc}': {err['msg']}")
    return "; ".join(parts[:3]) or "invalid payload"


def _system_messages(flag: FlaggedVariance, pnl: PnLResult) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "You are a finance controller's assistant investigating a flagged P&L variance. "
                "Call query_gl_detail to gather evidence (it is already scoped to THIS flag's line, "
                "period, and scenario — call it with no arguments, or pass filters to narrow to a "
                "counterparty/label), then call emit_investigation. "
                "You NEVER write a number and NEVER compute. Reference existing figures ONLY, by "
                "token, and only inside `narrative` (and `hypothesis_text`). The ONLY valid tokens "
                f"are: {{{{fig:flag.<field>}}}} where <field> is one of [{_FLAG_FIELDS}] — do NOT "
                "invent a field like 'direction'; {{fig:gl:<txn_id>.amount}} for a transaction "
                "query_gl_detail returned; and {{fig:agg:<id>}} for an aggregate you declare in "
                "`aggregates` ({agg_id, op: sum|count|min|max, row_ids}). To show a total or count, "
                "declare an aggregate — never write arithmetic such as '{{fig:a}} - {{fig:b}}' "
                "anywhere, and never put a token in any field other than narrative/hypothesis_text."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Flag {flag.flag_id}: {flag.reporting_line} {flag.time_cut.value} "
                f"{flag.scenario_pair.value}, direction {flag.direction}. "
                f"Reporting currency {pnl.reporting_currency}."
            ),
        },
    ]


def investigate(
    flag: FlaggedVariance,
    pnl: PnLResult,
    *,
    provider: LLMProvider,
    gl_tool: GLTool,
    settings: AgentSettings,
    audit: AuditLog,
    now: str,
) -> Optional[InvestigationRecord]:
    messages = _system_messages(flag, pnl)
    tools = [QUERY_GL_DETAIL_TOOL, EMIT_INVESTIGATION_TOOL]
    evidence: dict[str, GLEvidenceRow] = {}
    log_refs: list[str] = []
    tool_calls_used = 0
    guard_retries = 0
    forced = False  # once true, FORCE the model to call emit_investigation (no more prose/queries)
    prose_under_force = 0

    def log(response: dict) -> str:
        entry_id = audit.record(
            model=settings.model_id, request={"messages": messages}, response=response, now=now
        )
        log_refs.append(entry_id)
        return entry_id

    def fail_safe(reason: str) -> None:
        # PERMANENT, visible failure logging — an investigation must never vanish silently.
        logger.warning("investigation FAILED for flag=%s: %s", flag.flag_id, reason)
        audit.record(
            model=settings.model_id, request={"messages": messages},
            response={"error": reason}, now=now,
        )
        return None

    try:
        while True:
            choice = FORCE_EMIT if forced else "auto"
            resp = provider.complete(
                messages, tools, temperature=settings.temperature, model=settings.model_id,
                tool_choice=choice,
            )

            if isinstance(resp, ToolCall):
                log({"tool_call": resp.name, "arguments": resp.arguments})
                if resp.name != "query_gl_detail":
                    return fail_safe(f"unexpected tool call: {resp.name}")
                tool_calls_used += 1
                # DETERMINISTIC GROUNDING: the slice is the flag's own (line/time_cut/scenario/
                # as-of period); the model may only pass row filters. This prevents the model from
                # zeroing the result by inventing a scenario/period.
                query = grounded_gl_query(flag, pnl.current_period, (resp.arguments or {}).get("filters"))
                result = gl_tool(query)
                for row in result.rows:
                    evidence[row.transaction_id] = row
                messages.append(
                    {"role": "tool", "name": "query_gl_detail",
                     "content": f"returned {len(result.rows)} rows"}
                )
                if tool_calls_used >= settings.max_tool_calls_per_variance:
                    forced = True  # gathered enough; force the structured emit next
                continue

            if isinstance(resp, TextResponse):
                # The model replied in prose instead of calling a tool (the silent-drop cause).
                log({"text": resp.content[:1000]})
                if forced:
                    prose_under_force += 1
                    if prose_under_force > 1:
                        return fail_safe("model returned prose instead of structured output under forced emit")
                forced = True
                messages.append(
                    {"role": "user",
                     "content": "Do NOT answer in prose. Return your result by calling the "
                     "emit_investigation tool with structured arguments; reference every figure "
                     "by token (e.g. {{fig:gl:T1.amount}})."}
                )
                continue

            if isinstance(resp, StructuredFinal):
                log({"structured_final": resp.payload})
                try:
                    payload = EmitPayload(**resp.payload)
                except ValidationError as exc:
                    # Wrong-shaped emit (e.g. a fig-token/arithmetic string in `aggregates`).
                    reason = _emit_error_detail(exc)
                    logger.warning("flag=%s malformed emit payload: %s", flag.flag_id, reason)
                    if guard_retries >= settings.max_guard_retries:
                        return fail_safe(f"malformed emit payload: {reason}")
                    guard_retries += 1
                    forced = True
                    messages.append({"role": "user", "content": _retry_emit_prompt(reason)})
                    continue
                except Exception as exc:  # non-validation structural error (not retryable)
                    return fail_safe(f"malformed emit payload: {exc}")

                ev_list = [evidence[k] for k in sorted(evidence)]
                try:
                    rendered, figures, allowed = commentary.render_output(payload, ev_list, flag)
                except RenderError as exc:
                    # Bad token (unknown field, arithmetic between figures, undefined aggregate).
                    logger.warning("flag=%s emit rejected by renderer: %s", flag.flag_id, exc)
                    if guard_retries >= settings.max_guard_retries:
                        return fail_safe(f"render failed: {exc}")
                    guard_retries += 1
                    forced = True
                    messages.append({"role": "user", "content": _retry_emit_prompt(str(exc))})
                    continue

                g1 = assert_no_raw_digits(payload.narrative)
                g2 = assert_grounded(rendered, allowed)
                if g1.ok and g2.ok:
                    return _build_record(flag, payload, ev_list, rendered, figures, log_refs)

                # Guard rejected — log the rejected output + reason (still blocks bad numbers).
                logger.warning(
                    "flag=%s guard rejected output: raw_digits=%s ungrounded=%s text=%r",
                    flag.flag_id, g1.offending, g2.offending, rendered[:300],
                )
                if guard_retries >= settings.max_guard_retries:
                    return fail_safe(f"guard rejected: digits={g1.offending} grounded={g2.offending}")
                guard_retries += 1
                forced = True
                reason = (
                    f"ungrounded number(s) {g1.offending or g2.offending} not traceable to a cited figure"
                )
                messages.append({"role": "user", "content": _retry_emit_prompt(reason)})
                continue

            return fail_safe(f"unexpected provider response: {type(resp).__name__}")
    except Exception as exc:  # provider unavailable / transport error
        return fail_safe(f"provider error: {type(exc).__name__}: {exc}")


def _build_record(flag, payload: EmitPayload, evidence, text, figures, log_refs) -> InvestigationRecord:
    hypothesis = Hypothesis(text=payload.hypothesis_text, evidence_row_ids=payload.hypothesis_row_ids)
    question = None
    draft = None
    if payload.status is RecordStatus.QUESTION:
        question = commentary.build_question(flag, payload, evidence, text, figures, log_refs)
    else:  # self-explanatory → draft directly, no controller input
        draft = commentary.build_draft(flag, payload, evidence, text, figures, log_refs, None)
    return InvestigationRecord(
        flag_id=flag.flag_id,
        variance=flag,
        status=payload.status,
        evidence=evidence,
        hypothesis=hypothesis,
        question=question,
        draft=draft,
        llm_log_refs=log_refs,
    )


def draft_from_controller(
    flag: FlaggedVariance,
    evidence: list[GLEvidenceRow],
    controller_input: ControllerInput,
    *,
    provider: LLMProvider,
    settings: AgentSettings,
    audit: AuditLog,
    now: str,
) -> Optional[Draft]:
    """Draft commentary for a Question-status record once the controller has responded.

    Drafting is GATED on a controller response (FR-012): callers must supply `controller_input`.
    """
    if controller_input is None:
        raise ValueError("draft_from_controller requires a controller response (FR-012)")

    messages = [
        {"role": "system", "content": (
            "Draft a concise management-commentary line. You NEVER write a number and NEVER compute. "
            "Reference existing figures ONLY, by token, inside `narrative` (and `hypothesis_text`). "
            f"Valid tokens: {{{{fig:flag.<field>}}}} where <field> is one of [{_FLAG_FIELDS}]; "
            "{{fig:gl:<txn_id>.amount}}; {{fig:agg:<id>}} (declare it in `aggregates`). Never invent "
            "a field and never write arithmetic like '{{fig:a}} - {{fig:b}}'.")},
        {"role": "user", "content": f"Flag {flag.flag_id}. Controller confirmed: {controller_input.text}"},
    ]
    log_refs: list[str] = []
    guard_retries = 0
    prose_seen = 0
    try:
        while True:
            # Force the emit tool so the model returns structured output (not prose).
            resp = provider.complete(
                messages, [EMIT_INVESTIGATION_TOOL], temperature=settings.temperature,
                model=settings.model_id, tool_choice=FORCE_EMIT,
            )
            entry = audit.record(model=settings.model_id, request={"messages": messages},
                                 response={"structured_final": getattr(resp, "payload", None)}, now=now)
            log_refs.append(entry)
            if isinstance(resp, TextResponse):
                prose_seen += 1
                if prose_seen > 1:
                    logger.warning("draft_from_controller flag=%s: prose under forced emit", flag.flag_id)
                    return None
                messages.append({"role": "user", "content": "Call emit_investigation with structured arguments; no prose."})
                continue
            if not isinstance(resp, StructuredFinal):
                logger.warning("draft_from_controller flag=%s: unexpected response %s", flag.flag_id, type(resp).__name__)
                return None
            try:
                payload = EmitPayload(**resp.payload)
            except ValidationError as exc:
                reason = _emit_error_detail(exc)
                logger.warning("draft_from_controller flag=%s: malformed payload: %s", flag.flag_id, reason)
                if guard_retries >= settings.max_guard_retries:
                    return None
                guard_retries += 1
                messages.append({"role": "user", "content": _retry_emit_prompt(reason)})
                continue
            except Exception as exc:
                logger.warning("draft_from_controller flag=%s: malformed payload: %s", flag.flag_id, exc)
                return None
            try:
                rendered, figures, allowed = commentary.render_output(payload, evidence, flag)
            except RenderError as exc:
                logger.warning("draft_from_controller flag=%s: emit rejected by renderer: %s", flag.flag_id, exc)
                if guard_retries >= settings.max_guard_retries:
                    return None
                guard_retries += 1
                messages.append({"role": "user", "content": _retry_emit_prompt(str(exc))})
                continue
            if assert_no_raw_digits(payload.narrative).ok and assert_grounded(rendered, allowed).ok:
                return commentary.build_draft(flag, payload, evidence, rendered, figures, log_refs, controller_input)
            logger.warning("draft_from_controller flag=%s: guard rejected", flag.flag_id)
            if guard_retries >= settings.max_guard_retries:
                return None
            guard_retries += 1
            messages.append({"role": "user", "content": _retry_emit_prompt("ungrounded number not traceable to a cited figure")})
    except Exception as exc:
        logger.warning("draft_from_controller flag=%s: exception %s", flag.flag_id, exc)
        return None
