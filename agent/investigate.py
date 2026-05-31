"""The investigation loop (provider-agnostic agent core).

Given a flag + P&L context and the injected ports, run a bounded tool-call loop: the model
calls `query_gl_detail` to gather evidence, then emits a structured Question or Draft. Every
output passes the traceability guard (with one bounded retry); provider/parse failures
fail safe (logged, no ungrounded output). Contains NO SDK/HTTP calls.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

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
from agent.tools import QUERY_GL_DETAIL_TOOL
from agent.provider import FORCE_EMIT, LLMProvider, StructuredFinal, TextResponse, ToolCall

logger = logging.getLogger("variance_copilot.investigate")

EMIT_INVESTIGATION_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "emit_investigation",
        "description": "Emit the final investigation result: a question or a draft. "
        "Reference every figure by token (e.g. {{fig:gl:T1.amount}}); never write a digit.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["status", "narrative"],
            "properties": {
                "status": {"enum": ["question", "draft"]},
                "hypothesis_text": {"type": ["string", "null"]},
                "hypothesis_row_ids": {"type": "array", "items": {"type": "string"}},
                "narrative": {"type": "string"},
                "cited_row_ids": {"type": "array", "items": {"type": "string"}},
                "aggregates": {"type": "array"},
            },
        },
    },
}

GLTool = Callable[[GLQuery], "object"]


def _system_messages(flag: FlaggedVariance, pnl: PnLResult) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "You are a finance controller's assistant investigating a flagged P&L variance. "
                "Use query_gl_detail to gather evidence, then call emit_investigation. "
                "NEVER write a number: reference every figure by token "
                "({{fig:flag.<field>}}, {{fig:gl:<txn_id>.amount}}, {{fig:agg:<id>}})."
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
                result = gl_tool(GLQuery(**resp.arguments))
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
                except Exception as exc:  # malformed structured output
                    return fail_safe(f"malformed emit payload: {exc}")

                ev_list = [evidence[k] for k in sorted(evidence)]
                try:
                    rendered, figures, allowed = commentary.render_output(payload, ev_list, flag)
                except RenderError as exc:
                    if guard_retries >= settings.max_guard_retries:
                        return fail_safe(f"render failed: {exc}")
                    guard_retries += 1
                    forced = True
                    messages.append({"role": "user", "content": "Invalid figure token; retry via emit_investigation."})
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
                messages.append(
                    {"role": "user", "content": "Ungrounded number detected; reference figures by token only and retry via emit_investigation."}
                )
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
        {"role": "system", "content": "Draft a concise management-commentary line. Reference "
         "every figure by token; never write a digit."},
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
            except Exception as exc:
                logger.warning("draft_from_controller flag=%s: malformed payload: %s", flag.flag_id, exc)
                return None
            try:
                rendered, figures, allowed = commentary.render_output(payload, evidence, flag)
            except RenderError:
                if guard_retries >= settings.max_guard_retries:
                    return None
                guard_retries += 1
                messages.append({"role": "user", "content": "Invalid token; retry."})
                continue
            if assert_no_raw_digits(payload.narrative).ok and assert_grounded(rendered, allowed).ok:
                return commentary.build_draft(flag, payload, evidence, rendered, figures, log_refs, controller_input)
            logger.warning("draft_from_controller flag=%s: guard rejected", flag.flag_id)
            if guard_retries >= settings.max_guard_retries:
                return None
            guard_retries += 1
            messages.append({"role": "user", "content": "Ungrounded number; retry with tokens."})
    except Exception as exc:
        logger.warning("draft_from_controller flag=%s: exception %s", flag.flag_id, exc)
        return None
