"""US1 + retry (T037) + fail-safe (T036): the investigation loop with a fake provider (offline)."""

from __future__ import annotations

import pytest

from agent.fakes import FakeLLMProvider, final, text, tool_call
from agent.guards import draft_omits_available_evidence
from agent.investigate import investigate
from agent.models import RecordStatus
from agent.tools import grounded_gl_query


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


# --------------------------------------------------------------------------- #
# Emit-contract misuse: the model invents a figure field or expresses arithmetic.
# The bounded retry re-prompts once with the specific error, then fails safe (visible reason).
# --------------------------------------------------------------------------- #
def _errors(audit):
    return [e["response"]["error"] for e in audit.entries if "error" in e["response"]]


def test_unknown_figure_field_retries_then_recovers(ebitda_flag, result6, gl_tool6, agent_settings, audit):
    """Emit referencing an invented field ('direction') is rejected; the bounded retry recovers."""
    bad = final({"status": "draft", "narrative": "Variance is {{fig:flag.direction}}.", "aggregates": []})
    good = final({"status": "draft", "narrative": "EBITDA reached {{fig:flag.current_value}}.", "aggregates": []})
    provider = FakeLLMProvider([_query(ebitda_flag), bad, good])
    record = investigate(ebitda_flag, result6, provider=provider, gl_tool=gl_tool6,
                         settings=agent_settings, audit=audit, now="t")
    assert record is not None and record.status is RecordStatus.DRAFT


def test_persistent_unknown_field_fails_safe_with_visible_reason(ebitda_flag, result6, gl_tool6,
                                                                  agent_settings, audit):
    bad = final({"status": "draft", "narrative": "Variance is {{fig:flag.direction}}.", "aggregates": []})
    provider = FakeLLMProvider([_query(ebitda_flag), bad, bad])  # retry budget = 1
    record = investigate(ebitda_flag, result6, provider=provider, gl_tool=gl_tool6,
                         settings=agent_settings, audit=audit, now="t")
    assert record is None
    assert any("direction" in e for e in _errors(audit))  # the reason names the offending field


def test_arithmetic_in_narrative_fails_safe(ebitda_flag, result6, gl_tool6, agent_settings, audit):
    """Arithmetic between figure tokens in the narrative is rejected (no LLM-computed numbers)."""
    arith = final({"status": "draft",
                   "narrative": "Gap is {{fig:flag.current_value}} - {{fig:flag.comparator_value}}.",
                   "aggregates": []})
    provider = FakeLLMProvider([_query(ebitda_flag), arith, arith])
    record = investigate(ebitda_flag, result6, provider=provider, gl_tool=gl_tool6,
                         settings=agent_settings, audit=audit, now="t")
    assert record is None
    assert any("arithmetic" in e for e in _errors(audit))


def test_arithmetic_in_aggregate_field_fails_safe(ebitda_flag, result6, gl_tool6, agent_settings, audit):
    """A fig-token/arithmetic STRING in the structured `aggregates` field fails cleanly."""
    badagg = {"status": "draft", "narrative": "Total {{fig:agg:a1}}.",
              "aggregates": ["{{fig:gl:T1.amount}} - {{fig:gl:T2.amount}}"]}
    provider = FakeLLMProvider([_query(ebitda_flag), final(badagg), final(badagg)])
    record = investigate(ebitda_flag, result6, provider=provider, gl_tool=gl_tool6,
                         settings=agent_settings, audit=audit, now="t")
    assert record is None
    assert any("aggregates" in e for e in _errors(audit))  # the reason names the offending field


# --------------------------------------------------------------------------- #
# Deterministic GL grounding: the query is scoped to the flag's own slice, so the driver rows
# come back on the LIVE call path regardless of what (if anything) the model passes.
# --------------------------------------------------------------------------- #
def _flag(flags6, line, time_cut="current_month", pair="current_vs_prior_year"):
    return next(f for f in flags6 if f.reporting_line == line
                and f.time_cut.value == time_cut and f.scenario_pair.value == pair)


# (reporting_line, expected driver transaction id, its counterparty)
_DRIVERS = [
    ("it_costs", "current_year-7200-P06-2", "DataPlatform Inc"),        # Annual license - DataPlatform
    ("subcontracting_costs", "current_year-5000-P06-1", "Atlas Digital Ltd"),  # project ramp-up
    ("media_space_costs", "current_year-5300-P06-2", "MediaBuy Co"),    # Campaign Mar-2026
]


@pytest.mark.parametrize("line,driver_txn,counterparty", _DRIVERS)
def test_live_path_returns_driver_rows_for_each_flagged_line(
    line, driver_txn, counterparty, flags6, result6, gl_tool6, agent_settings, audit
):
    """The model calls query_gl_detail with NO dimensional args (the new schema); the agent grounds
    the slice itself and the driver rows come back as evidence."""
    flag = _flag(flags6, line)
    provider = FakeLLMProvider([
        tool_call("query_gl_detail", {}),  # model passes nothing — slice is grounded by the agent
        final({"status": "draft", "narrative": "{{fig:flag.current_value}} driven by GL detail.",
               "aggregates": []}),
    ])
    record = investigate(flag, result6, provider=provider, gl_tool=gl_tool6,
                         settings=agent_settings, audit=audit, now="t")
    assert record is not None and record.status is RecordStatus.DRAFT
    txn_ids = {r.transaction_id for r in record.evidence}
    assert driver_txn in txn_ids, f"{line}: driver {driver_txn} missing from evidence {txn_ids}"
    assert any(r.counterparty == counterparty for r in record.evidence)


def test_grounded_query_returns_rows_even_if_model_would_pass_wrong_scenario(flags6, result6, gl_tool6):
    """Regression: the OLD bug was the model stuffing the pair into `scenario` → 0 rows. The slice
    is now fixed by the flag, so the grounded query always returns the line's rows."""
    flag = _flag(flags6, "it_costs")
    rows = gl_tool6(grounded_gl_query(flag, result6.current_period)).rows
    assert rows, "grounded query must return the flagged line's GL rows"
    assert all(r.gl_account == "7200" and r.period == 6 and r.scenario == "current_year" for r in rows)


def test_draft_omitting_existing_evidence_is_flagged(flags6, result6, gl_tool6, agent_settings, audit):
    """A self-explanatory draft emitted WITHOUT gathering evidence — while GL rows exist for the
    line/period — is a bug the check catches."""
    flag = _flag(flags6, "it_costs")
    rows_exist = bool(gl_tool6(grounded_gl_query(flag, result6.current_period)).rows)
    assert rows_exist
    provider = FakeLLMProvider([  # straight to a draft, no query → no evidence gathered
        final({"status": "draft",
               "narrative": "The variance {{fig:flag.abs_variance}} is above the threshold.",
               "aggregates": []}),
    ])
    record = investigate(flag, result6, provider=provider, gl_tool=gl_tool6,
                         settings=agent_settings, audit=audit, now="t")
    assert record is not None and record.status is RecordStatus.DRAFT
    assert record.evidence == []  # the bug: drafted with no evidence
    assert draft_omits_available_evidence(record, rows_exist) is True


def test_draft_with_gathered_evidence_passes_check(flags6, result6, gl_tool6, agent_settings, audit):
    flag = _flag(flags6, "it_costs")
    rows_exist = bool(gl_tool6(grounded_gl_query(flag, result6.current_period)).rows)
    provider = FakeLLMProvider([
        tool_call("query_gl_detail", {}),
        final({"status": "draft", "narrative": "{{fig:flag.current_value}} per the GL.", "aggregates": []}),
    ])
    record = investigate(flag, result6, provider=provider, gl_tool=gl_tool6,
                         settings=agent_settings, audit=audit, now="t")
    assert record.evidence
    assert draft_omits_available_evidence(record, rows_exist) is False
