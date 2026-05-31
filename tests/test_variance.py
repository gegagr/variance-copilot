"""US3 tests: variance computation (FR-010/011/012/013)."""

from __future__ import annotations

from decimal import Decimal

from engine.models import (
    LineType,
    ScenarioPair,
    TimeCut,
    Variance,
)


def _find(variances, line, tc, pair) -> Variance:
    return next(
        v for v in variances
        if v.reporting_line == line and v.time_cut == tc and v.scenario_pair == pair
    )


def test_absolute_variance_is_current_minus_comparator(variances6):
    # external_revenue current month: current 215000 (revenue-mix dip), prior 230000.
    v = _find(variances6, "external_revenue", TimeCut.CURRENT_MONTH, ScenarioPair.CURRENT_VS_PRIOR_YEAR)
    assert v.current_value == Decimal("215000.00")
    assert v.comparator_value == Decimal("230000.00")
    assert v.abs_variance == Decimal("-15000.00")


def test_percentage_uses_absolute_denominator(variances6):
    v = _find(variances6, "external_revenue", TimeCut.CURRENT_MONTH, ScenarioPair.CURRENT_VS_PRIOR_YEAR)
    assert v.pct_variance == (Decimal("-15000.00") / Decimal("230000.00")).quantize(Decimal("0.000001"))


def test_negative_comparator_keeps_intuitive_magnitude(variances6):
    """subcontracting is negative; % must use |comparator| so the sign isn't flipped."""
    v = _find(variances6, "subcontracting_costs", TimeCut.CURRENT_MONTH, ScenarioPair.CURRENT_VS_PRIOR_YEAR)
    # current -15000 (Atlas ramp-up), prior -10000 -> abs -5000 ; pct = -5000/10000 = -0.5
    assert v.abs_variance == Decimal("-5000.00")
    assert v.pct_variance == Decimal("-0.500000")


def test_margin_variance_is_percentage_points(variances6):
    v = _find(variances6, "gross_margin_pct", TimeCut.CURRENT_MONTH, ScenarioPair.CURRENT_VS_PRIOR_YEAR)
    assert v.line_type is LineType.MARGIN
    assert v.abs_variance is None and v.pct_variance is None
    # gm% current 226000/275000=0.821818 ; prior 245000/275000=0.890909 -> -0.069091 pp
    assert v.pp_variance == Decimal("-0.069091")


def test_favorable_unfavorable_by_line_type(variances6):
    # Revenue down vs prior -> unfavorable; staff costs UNDER budget (less spend) -> favorable.
    rev = _find(variances6, "external_revenue", TimeCut.CURRENT_MONTH, ScenarioPair.CURRENT_VS_PRIOR_YEAR)
    staff = _find(variances6, "staff_costs", TimeCut.CURRENT_MONTH, ScenarioPair.CURRENT_VS_BUDGET)
    assert rev.direction == "unfavorable"
    assert staff.direction == "favorable"


def test_zero_comparator_marked_not_meaningful():
    from engine.variance import compute_variances
    from engine.pnl import build_pnl
    from engine.models import Scenario
    from tests.conftest import minimal_config, tx

    cfg = minimal_config(current_period=1)
    # current-year revenue exists; prior-year revenue absent -> comparator 0.
    txns = [tx("t1", "R", "500.00", 1, Scenario.CURRENT_YEAR)]
    result = build_pnl(txns, cfg)
    variances = compute_variances(result, cfg)
    v = _find(variances, "revenue", TimeCut.CURRENT_MONTH, ScenarioPair.CURRENT_VS_PRIOR_YEAR)
    assert v.comparator_value == Decimal("0.00")
    assert v.pct_variance is None
    assert v.is_meaningful is False
    assert v.abs_variance == Decimal("500.00")
