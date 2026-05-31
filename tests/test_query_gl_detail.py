"""Foundational: query_gl_detail tool contract (read-only, correct rows)."""

from __future__ import annotations

from decimal import Decimal

from agent.models import GLQuery
from agent.tools import gl_accounts_for, query_gl_detail
from data.gl_detail_repository import GLDetailRepository
from tests.conftest import SAMPLE_DIR


def _repo():
    return GLDetailRepository(SAMPLE_DIR)


def test_leaf_line_returns_its_accounts_rows(cfg6):
    res = query_gl_detail(_repo(), cfg6, GLQuery(reporting_line="subcontracting_costs", period=6, scenario="current_year"))
    assert res.rows
    assert {r.gl_account for r in res.rows} == {"5000"}
    assert all(r.period == 6 and r.scenario == "current_year" for r in res.rows)


def test_subtotal_returns_union_of_component_accounts(cfg6):
    # ebitda rolls up every detail line above it (revenue + all costs down to premises).
    accounts = gl_accounts_for(cfg6, "ebitda")
    assert accounts == {
        "4000", "4100", "5000", "5100", "5200", "5300",
        "6000", "6100", "6200", "6300", "7000", "7100", "7200", "7300",
    }


def test_filters_narrow_results(cfg6):
    # The late-booked media row carries the "Campaign Mar-2026" label this month.
    res = query_gl_detail(
        _repo(), cfg6,
        GLQuery(reporting_line="media_space_costs", period=6, scenario="current_year",
                filters={"label": "Campaign Mar-2026"}),
    )
    assert len(res.rows) == 1
    assert "Campaign Mar-2026" in res.rows[0].labels


def test_canonical_row_order(cfg6):
    res = query_gl_detail(_repo(), cfg6, GLQuery(reporting_line="external_revenue", period=3, scenario="prior_year"))
    ids = [r.transaction_id for r in res.rows]
    assert ids == sorted(ids)


def test_flag_dimensions_map_to_data_columns(cfg6):
    """A flag carries time_cut/scenario_pair, not period/scenario; the query must translate.

    current_month (current_period=6) -> period 6; current_vs_prior_year -> the CURRENT side
    = current-year actuals. The slice must include both the recurring media buy and the
    late-booked €8k 'Campaign Mar-2026' row, all from scenario == current_year.
    """
    res = query_gl_detail(
        _repo(), cfg6,
        GLQuery(reporting_line="media_space_costs",
                time_cut="current_month", scenario_pair="current_vs_prior_year"),
    )
    assert res.rows, "flag-dimension query returned zero rows (mapping is broken)"
    assert all(r.scenario == "current_year" and r.period == 6 for r in res.rows)
    assert {r.gl_account for r in res.rows} == {"5300"}
    # the deliberate anomaly: the €8k March-labelled campaign booked in period 6
    campaign = next(r for r in res.rows if "Campaign Mar-2026" in r.labels)
    assert campaign.amount == Decimal("-8000.00")


def test_time_cut_ytd_spans_periods_one_through_current(cfg6):
    """YTD must resolve to periods 1..6 of current-year actuals (mirrors the engine)."""
    res = query_gl_detail(
        _repo(), cfg6,
        GLQuery(reporting_line="media_space_costs",
                time_cut="ytd", scenario_pair="current_vs_prior_year"),
    )
    assert {r.period for r in res.rows} == {1, 2, 3, 4, 5, 6}
    assert all(r.scenario == "current_year" for r in res.rows)
