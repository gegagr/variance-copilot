"""US4 tests: materiality flagging logic (FR-015/016)."""

from __future__ import annotations

from decimal import Decimal

from engine.flagging import flag_variances
from engine.models import LineType, ScenarioPair, TimeCut, Variance


def _value_variance(abs_v, pct_v, line_type=LineType.REVENUE):
    return Variance(
        reporting_line="x", line_type=line_type, time_cut=TimeCut.YTD,
        scenario_pair=ScenarioPair.CURRENT_VS_BUDGET,
        current_value=Decimal("100"), comparator_value=Decimal("100"),
        abs_variance=Decimal(abs_v), pct_variance=Decimal(pct_v),
        direction="favorable",
    )


def _subtotal_variance(abs_v, pct_v):
    return Variance(
        reporting_line="s", line_type=LineType.SUBTOTAL, time_cut=TimeCut.YTD,
        scenario_pair=ScenarioPair.CURRENT_VS_BUDGET,
        current_value=Decimal("100"), comparator_value=Decimal("100"),
        abs_variance=Decimal(abs_v), pct_variance=Decimal(pct_v), direction="favorable",
    )


def _margin_variance(pp_v):
    return Variance(
        reporting_line="m", line_type=LineType.MARGIN, time_cut=TimeCut.YTD,
        scenario_pair=ScenarioPair.CURRENT_VS_BUDGET,
        current_value=Decimal("0.5"), comparator_value=Decimal("0.45"),
        pp_variance=Decimal(pp_v), direction="favorable",
    )


def test_value_line_flags_only_when_both_abs_and_pct_breach(cfg6):
    # thresholds: abs 4000, pct 0.05
    both = _value_variance("20000", "0.10")          # both breach -> flag
    only_abs = _value_variance("20000", "0.01")      # pct below -> no flag
    only_pct = _value_variance("500", "0.10")        # abs below -> no flag
    flags = flag_variances([both, only_abs, only_pct], cfg6)
    assert len(flags) == 1
    assert flags[0].abs_variance == Decimal("20000")


def test_subtotals_and_margins_are_never_flagged(cfg6):
    """Only detail lines are flagged; roll-ups (subtotal/margin) never are, even when material."""
    subtotal = _subtotal_variance("50000", "0.50")   # huge breach, but it's a subtotal
    margin = _margin_variance("0.20")                 # huge pp move, but it's a margin
    detail = _value_variance("20000", "0.10", LineType.COST)  # a detail line -> flags
    flags = flag_variances([subtotal, margin, detail], cfg6)
    assert len(flags) == 1
    assert flags[0].line_type is LineType.COST


def test_real_flags_are_all_detail_lines(flags6):
    assert flags6
    assert all(f.line_type in (LineType.REVENUE, LineType.COST) for f in flags6)


def test_flag_has_all_required_fields(flags6):
    assert flags6, "expected at least one flag from the sample data"
    for f in flags6:
        assert f.schema_version == "1.0.0"
        assert f.flag_id and f.rule_id and f.reporting_line
        assert f.direction in ("favorable", "unfavorable")
        assert f.abs_threshold is not None
        assert f.pct_threshold is not None
        assert f.pp_threshold is not None


def test_flag_id_is_deterministic(variances6, cfg6):
    a = flag_variances(variances6, cfg6)
    b = flag_variances(list(reversed(variances6)), cfg6)
    assert [f.flag_id for f in a] == [f.flag_id for f in b]


def test_neutral_direction_never_flagged(cfg6):
    neutral = _value_variance("20000", "0.10")
    neutral = neutral.model_copy(update={"direction": "neutral"})
    assert flag_variances([neutral], cfg6) == []
