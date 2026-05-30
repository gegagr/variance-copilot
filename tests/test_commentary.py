"""US2/US3 commentary rendering: reference→render, aggregates, draft-from-controller gating."""

from __future__ import annotations

from decimal import Decimal

import pytest

from agent import commentary
from agent.fakes import FakeLLMProvider, final
from agent.investigate import draft_from_controller
from agent.models import (
    AggregateOp,
    AggregateSpec,
    ControllerInput,
    EmitPayload,
    GLEvidenceRow,
)


def _rows():
    return [
        GLEvidenceRow(transaction_id="T1", gl_account="5000", amount=Decimal("-4240.00"),
                      period=6, scenario="current_year", date="2026-06-15", labels=["late_booking"]),
        GLEvidenceRow(transaction_id="T2", gl_account="5000", amount=Decimal("-4240.00"),
                      period=6, scenario="current_year", date="2026-06-15", labels=[]),
    ]


def test_render_substitutes_flag_and_gl_figures(ebitda_flag):
    payload = EmitPayload(
        status="draft",
        narrative="EBITDA {{fig:flag.current_value}}; one invoice {{fig:gl:T1.amount}}.",
    )
    text, figures, allowed = commentary.render_output(payload, _rows(), ebitda_flag)
    assert "{{" not in text  # all tokens resolved
    assert "€" in text
    assert {f.source.value for f in figures} == {"block1", "gl"}


def test_render_computes_aggregate(ebitda_flag):
    payload = EmitPayload(
        status="draft",
        narrative="Two invoices totalling {{fig:agg:a1}}.",
        aggregates=[AggregateSpec(agg_id="a1", op=AggregateOp.SUM, row_ids=["T1", "T2"])],
    )
    text, figures, allowed = commentary.render_output(payload, _rows(), ebitda_flag)
    # sum of -4240 + -4240 = -8480.00, code-computed and in the allowed money set.
    assert Decimal("-8480.00") in allowed.money
    assert any(f.source.value == "aggregate" for f in figures)
    assert "€-8,480.00" in text


def test_draft_from_controller_requires_response(ebitda_flag, agent_settings, audit):
    with pytest.raises(ValueError):
        draft_from_controller(ebitda_flag, _rows(), None, provider=FakeLLMProvider([]),
                              settings=agent_settings, audit=audit, now="t")


def test_draft_from_controller_reflects_response(ebitda_flag, agent_settings, audit):
    ci = ControllerInput(input_id="ci1", flag_id=ebitda_flag.flag_id,
                         text="Late-booked supplier invoice from December.", accepted_hypothesis=True)
    provider = FakeLLMProvider([
        final({"status": "draft",
               "narrative": "EBITDA variance driven by a late-booked invoice {{fig:gl:T1.amount}}.",
               "aggregates": []}),
    ])
    draft = draft_from_controller(ebitda_flag, _rows(), ci, provider=provider,
                                  settings=agent_settings, audit=audit, now="t")
    assert draft is not None
    assert draft.controller_input.input_id == "ci1"
    assert draft.provenance.controller_input_id == "ci1"
    assert draft.is_proposal is True
