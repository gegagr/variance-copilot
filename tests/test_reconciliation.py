"""US1 reconciliation tests: subtotals, margins, and ties-to-source (FR-004/005/027)."""

from __future__ import annotations

from decimal import Decimal

from engine.models import SCENARIO_ORDER, TIMECUT_ORDER, LineType, Scenario, TimeCut
from engine.periods import contributions
from tests.conftest import cells_by_key


def test_subtotals_equal_sum_of_components(result6, cfg6):
    cells = cells_by_key(result6)
    layout = {row.reporting_line: row for row in cfg6.layout}
    for line in result6.lines:
        row = layout[line.reporting_line]
        if row.line_type is not LineType.SUBTOTAL:
            continue
        for scenario in SCENARIO_ORDER:
            for tc in TIMECUT_ORDER:
                expected = sum(
                    (cells[(comp, scenario, tc)].value for comp in row.components),
                    Decimal(0),
                )
                assert cells[(line.reporting_line, scenario, tc)].value == expected


def test_margins_equal_numerator_over_base(result6, cfg6):
    cells = cells_by_key(result6)
    layout = {row.reporting_line: row for row in cfg6.layout}
    rp = cfg6.settings.ratio_precision
    for line in result6.lines:
        row = layout[line.reporting_line]
        if row.line_type is not LineType.MARGIN:
            continue
        for scenario in SCENARIO_ORDER:
            for tc in TIMECUT_ORDER:
                num = cells[(row.margin_numerator, scenario, tc)].value
                base = cells[(row.margin_base, scenario, tc)].value
                got = cells[(line.reporting_line, scenario, tc)].value
                if base == 0:
                    assert got == 0
                else:
                    assert got == (num / base).quantize(Decimal(1).scaleb(-rp))


def test_ties_to_source_zero_residual(result6, transactions):
    """Each leaf cell equals the independent sum of its source transactions."""
    cells = cells_by_key(result6)
    coa = {"4000": "revenue", "4001": "revenue", "5000": "cogs",
           "6000": "opex", "6001": "opex", "7000": "depreciation"}
    p = result6.current_period

    for line in ("revenue", "cogs", "opex", "depreciation"):
        for scenario in SCENARIO_ORDER:
            for tc in TIMECUT_ORDER:
                expected = Decimal(0)
                for src_scenario, prds in contributions(scenario, tc, p):
                    for t in transactions:
                        if (coa.get(t.gl_account) == line and t.scenario == src_scenario
                                and t.period in prds):
                            expected += t.amount
                assert cells[(line, scenario, tc)].value == expected

    assert result6.reconciliation.is_complete
    assert result6.reconciliation.residual == Decimal("0.00")


def test_grand_total_ebit_ties_to_all_mapped_transactions(result6, transactions):
    """EBIT (sum of every leaf) over the full year ties to the source totals."""
    cells = cells_by_key(result6)
    # Prior-year full year is pure actuals across all 12 periods.
    expected = sum(
        (t.amount for t in transactions if t.scenario == Scenario.PRIOR_YEAR),
        Decimal(0),
    )
    assert cells[("ebit", Scenario.PRIOR_YEAR, TimeCut.FULL_YEAR)].value == expected
