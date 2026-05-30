"""US2 tests: scenarios x time cuts and the labeled landing (FR-006/007/008/009)."""

from __future__ import annotations

from decimal import Decimal

from config.loader import load_config
from data.fixture_repository import FixtureRepository
from engine.models import Scenario, TimeCut, ValueKind
from engine.pnl import build_pnl
from tests.conftest import CONFIG_DIR, SAMPLE_DIR, cells_by_key


def _result_at(period: int):
    cfg = load_config(CONFIG_DIR, current_period=period)
    txns = FixtureRepository(SAMPLE_DIR).get_transactions()
    return build_pnl(txns, cfg), cfg


def test_landing_is_elapsed_actual_plus_remaining_budget(transactions):
    result, _ = _result_at(6)
    cells = cells_by_key(result)
    # revenue per entity per period: actual 13440, budget 12600; 2 entities.
    elapsed_actual = Decimal("13440.00") * 6 * 2
    remaining_budget = Decimal("12600.00") * 6 * 2
    landing = cells[("revenue", Scenario.CURRENT_YEAR, TimeCut.FULL_YEAR)]
    assert landing.value == elapsed_actual + remaining_budget
    assert landing.value_kind is ValueKind.LANDING


def test_landing_distinct_from_ytd_actual():
    result, _ = _result_at(6)
    cells = cells_by_key(result)
    ytd = cells[("revenue", Scenario.CURRENT_YEAR, TimeCut.YTD)]
    landing = cells[("revenue", Scenario.CURRENT_YEAR, TimeCut.FULL_YEAR)]
    assert ytd.value != landing.value
    assert ytd.value_kind is ValueKind.ACTUAL
    assert landing.value_kind is ValueKind.LANDING


def test_landing_label_present_on_all_current_year_full_year_cells():
    result, _ = _result_at(6)
    for line in result.lines:
        for c in line.cells:
            if c.scenario is Scenario.CURRENT_YEAR and c.time_cut is TimeCut.FULL_YEAR:
                # value cells are LANDING; a zero-base margin would be NOT_MEANINGFUL.
                assert c.value_kind in (ValueKind.LANDING, ValueKind.NOT_MEANINGFUL)


def test_boundary_first_period_empty_prior_month_ytd():
    result, _ = _result_at(1)
    cells = cells_by_key(result)
    # prior_month_ytd = periods 1..0 = empty -> zero, no failure.
    assert cells[("revenue", Scenario.CURRENT_YEAR, TimeCut.PRIOR_MONTH_YTD)].value == Decimal("0.00")


def test_boundary_last_period_landing_equals_ytd():
    result, _ = _result_at(12)
    cells = cells_by_key(result)
    ytd = cells[("revenue", Scenario.CURRENT_YEAR, TimeCut.YTD)]
    landing = cells[("revenue", Scenario.CURRENT_YEAR, TimeCut.FULL_YEAR)]
    # At p=12 there is no remaining budget, so landing == YTD actual (but still labeled landing).
    assert landing.value == ytd.value
    assert landing.value_kind is ValueKind.LANDING


def test_all_scenarios_and_time_cuts_present(result6):
    for line in result6.lines:
        keys = {(c.scenario, c.time_cut) for c in line.cells}
        assert len(keys) == 3 * 4  # 3 scenarios x 4 time cuts
