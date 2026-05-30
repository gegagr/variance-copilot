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
    v = _find(variances6, "revenue", TimeCut.YTD, ScenarioPair.CURRENT_VS_PRIOR_YEAR)
    # revenue YTD: current 161280, prior 144000.
    assert v.current_value == Decimal("161280.00")
    assert v.comparator_value == Decimal("144000.00")
    assert v.abs_variance == Decimal("17280.00")


def test_percentage_uses_absolute_denominator(variances6):
    v = _find(variances6, "revenue", TimeCut.YTD, ScenarioPair.CURRENT_VS_PRIOR_YEAR)
    assert v.pct_variance == (Decimal("17280.00") / Decimal("144000.00")).quantize(Decimal("0.000001"))


def test_negative_comparator_keeps_intuitive_magnitude(variances6):
    """cogs is negative; % must use |comparator| so the sign isn't flipped."""
    v = _find(variances6, "cogs", TimeCut.YTD, ScenarioPair.CURRENT_VS_PRIOR_YEAR)
    # current -50880, prior -48000 -> abs var -2880 ; pct = -2880/48000 = -0.06
    assert v.abs_variance == Decimal("-2880.00")
    assert v.pct_variance == Decimal("-0.060000")


def test_margin_variance_is_percentage_points(variances6):
    v = _find(variances6, "gross_margin_pct", TimeCut.YTD, ScenarioPair.CURRENT_VS_PRIOR_YEAR)
    assert v.line_type is LineType.MARGIN
    assert v.abs_variance is None and v.pct_variance is None
    # 0.684524 - 0.666667 = 0.017857
    assert v.pp_variance == Decimal("0.017857")


def test_favorable_unfavorable_by_line_type(variances6):
    rev = _find(variances6, "revenue", TimeCut.YTD, ScenarioPair.CURRENT_VS_PRIOR_YEAR)
    cogs = _find(variances6, "cogs", TimeCut.YTD, ScenarioPair.CURRENT_VS_PRIOR_YEAR)
    # Revenue up -> favorable; cost more negative (higher spend) -> unfavorable.
    assert rev.direction == "favorable"
    assert cogs.direction == "unfavorable"


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
