"""Time-cut selection and the landing estimate (pure).

The current period ``p`` is an explicit input (never the wall clock), so the
YTD/landing split is a pure function of inputs and is fully testable.
"""

from __future__ import annotations

from engine.models import Scenario, TimeCut, ValueKind

FISCAL_PERIODS = tuple(range(1, 13))  # 1..12


def periods_for(time_cut: TimeCut, current_period: int) -> list[int]:
    """Return the fiscal periods contributing to ``time_cut`` for a same-scenario cut."""
    p = current_period
    if time_cut is TimeCut.PRIOR_MONTH_YTD:
        return list(range(1, p))          # 1..p-1 (empty when p == 1)
    if time_cut is TimeCut.CURRENT_MONTH:
        return [p]
    if time_cut is TimeCut.YTD:
        return list(range(1, p + 1))      # 1..p
    if time_cut is TimeCut.FULL_YEAR:
        return list(FISCAL_PERIODS)       # 1..12
    raise ValueError(f"Unknown time cut: {time_cut}")


def contributions(
    scenario: Scenario, time_cut: TimeCut, current_period: int
) -> list[tuple[Scenario, list[int]]]:
    """Return the (source scenario, periods) contributions feeding a cell.

    The only blended cell is the current-year FULL_YEAR landing: current-year
    actuals for elapsed periods plus budget for the remaining periods.
    """
    p = current_period
    if scenario is Scenario.CURRENT_YEAR and time_cut is TimeCut.FULL_YEAR:
        return [
            (Scenario.CURRENT_YEAR, list(range(1, p + 1))),   # actuals 1..p
            (Scenario.BUDGET, list(range(p + 1, 13))),        # budget p+1..12
        ]
    return [(scenario, periods_for(time_cut, current_period))]


def value_kind(
    scenario: Scenario, time_cut: TimeCut, is_margin: bool, zero_base: bool
) -> ValueKind:
    """Classify a cell so actuals and the landing are never conflated."""
    if is_margin and zero_base:
        return ValueKind.NOT_MEANINGFUL
    if scenario is Scenario.CURRENT_YEAR and time_cut is TimeCut.FULL_YEAR:
        return ValueKind.LANDING
    if scenario is Scenario.BUDGET:
        return ValueKind.BUDGET
    return ValueKind.ACTUAL
