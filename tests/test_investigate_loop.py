"""US1 + retry (T037) + fail-safe (T036): the investigation loop with a fake provider (offline)."""

from __future__ import annotations

from agent.fakes import FakeLLMProvider, final, text, tool_call
from agent.investigate import investigate
from agent.models import RecordStatus


def _query(flag):
    # current_month at p=6 → period 6, current_year actuals.
    return tool_call("query_gl_detail", {"reporting_line": flag.reporting_line, "period": 6, "scenario": "current_year"})


def test_prose_completion_is_recovered_by_forcing_emit(ebitda_flag, result6, gl_tool6, agent_settings, audit):
    """The reported bug: the model answers in prose (no tool call). The loop must NOT drop it —
    it forces emit_investigation and recovers a record."""
    good = final({"status": "draft", "narrative": "EBITDA reached {{fig:flag.current_value}}.", "aggregates": []})
    provider = FakeLLMProvider([text("EBITDA looks fine to me."), good])  # prose first, then structured
    record = investigate(ebitda_flag, result6, provider=provider, gl_tool=gl_tool6,
                         settings=agent_settings, audit=audit, now="t")
    assert record is not None and record.status is RecordStatus.DRAFT
    # the second call was issued with forced emit
    assert provider.calls[-1]["tool_choice"] != "auto"


def test_persistent_prose_fails_safe(ebitda_flag, result6, gl_tool6, agent_settings, audit):
    provider = FakeLLMProvider([text("prose one"), text("prose two"), text("prose three")])
    record = investigate(ebitda_flag, result6, provider=provider, gl_tool=gl_tool6,
                         settings=agent_settings, audit=audit, now="t")
    assert record is None
    assert any("error" in e["response"] for e in audit.entries)


def test_loop_gathers_evidence_and_drafts(ebitda_flag, result6, gl_tool6, agent_settings, audit):
    provider = FakeLLMProvider([
        _query(ebitda_flag),
        final({
            "status": "draft",
            "hypothesis_text": "EBITDA outperformed on revenue growth.",
            "hypothesis_row_ids": [],
            "narrative": "EBITDA reached {{fig:flag.current_value}} versus {{fig:flag.comparator_value}} prior year.",
            "cited_row_ids": [],
            "aggregates": [],
        }),
    ])
    record = investigate(ebitda_flag, result6, provider=provider, gl_tool=gl_tool6,
                         settings=agent_settings, audit=audit, now="2026-05-30T00:00:00Z")
    assert record is not None
    assert record.status is RecordStatus.DRAFT
    assert record.evidence, "evidence should be embedded from the query"
    assert record.draft is not None
    assert len(record.draft.rendered_figures) == 2
    assert record.llm_log_refs  # linked to audit entries


def test_sparse_evidence_yields_open_question(ebitda_flag, result6, gl_tool6, agent_settings, audit):
    provider = FakeLLMProvider([
        final({
            "status": "question",
            "hypothesis_text": None,
            "hypothesis_row_ids": [],
            "narrative": "We could not identify a clear driver from the ledger. Can you add context?",
            "cited_row_ids": [],
            "aggregates": [],
        }),
    ])
    record = investigate(ebitda_flag, result6, provider=provider, gl_tool=gl_tool6,
                         settings=agent_settings, audit=audit, now="2026-05-30T00:00:00Z")
    assert record is not None
    assert record.status is RecordStatus.QUESTION
    assert record.hypothesis.text is None
    assert record.question is not None


def test_bounded_retry_recovers_from_one_ungrounded_output(ebitda_flag, result6, gl_tool6, agent_settings, audit):
    bad = final({"status": "draft", "narrative": "EBITDA rose 5% this period.", "aggregates": []})  # raw digit
    good = final({"status": "draft", "narrative": "EBITDA reached {{fig:flag.current_value}}.", "aggregates": []})
    provider = FakeLLMProvider([_query(ebitda_flag), bad, good])
    record = investigate(ebitda_flag, result6, provider=provider, gl_tool=gl_tool6,
                         settings=agent_settings, audit=audit, now="2026-05-30T00:00:00Z")
    assert record is not None and record.status is RecordStatus.DRAFT


def test_failsafe_when_retries_exhausted(ebitda_flag, result6, gl_tool6, agent_settings, audit):
    bad = final({"status": "draft", "narrative": "EBITDA rose 5%.", "aggregates": []})
    provider = FakeLLMProvider([_query(ebitda_flag), bad, bad])  # bad twice (retry budget = 1)
    record = investigate(ebitda_flag, result6, provider=provider, gl_tool=gl_tool6,
                         settings=agent_settings, audit=audit, now="2026-05-30T00:00:00Z")
    assert record is None
    assert any("error" in e["response"] for e in audit.entries)  # failure logged


def test_failsafe_on_provider_error(ebitda_flag, result6, gl_tool6, agent_settings, audit):
    provider = FakeLLMProvider([RuntimeError("model unavailable")])
    record = investigate(ebitda_flag, result6, provider=provider, gl_tool=gl_tool6,
                         settings=agent_settings, audit=audit, now="2026-05-30T00:00:00Z")
    assert record is None
    assert any("error" in e["response"] for e in audit.entries)


def test_failsafe_on_malformed_output(ebitda_flag, result6, gl_tool6, agent_settings, audit):
    provider = FakeLLMProvider([final({"status": "not_a_status", "narrative": "x"})])
    record = investigate(ebitda_flag, result6, provider=provider, gl_tool=gl_tool6,
                         settings=agent_settings, audit=audit, now="2026-05-30T00:00:00Z")
    assert record is None
