"""Foundational: query_gl_detail tool contract (read-only, correct rows)."""

from __future__ import annotations

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
