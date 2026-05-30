"""Foundational: query_gl_detail tool contract (read-only, correct rows)."""

from __future__ import annotations

from agent.models import GLQuery
from agent.tools import gl_accounts_for, query_gl_detail
from data.gl_detail_repository import GLDetailRepository
from tests.conftest import SAMPLE_DIR


def _repo():
    return GLDetailRepository(SAMPLE_DIR)


def test_leaf_line_returns_its_accounts_rows(cfg6):
    res = query_gl_detail(_repo(), cfg6, GLQuery(reporting_line="cogs", period=6, scenario="current_year"))
    assert res.rows
    assert {r.gl_account for r in res.rows} == {"5000"}
    assert all(r.period == 6 and r.scenario == "current_year" for r in res.rows)


def test_subtotal_returns_union_of_component_accounts(cfg6):
    # ebitda = gross_profit(revenue,cogs) + opex  ->  accounts 4000,4001,5000,6000,6001
    accounts = gl_accounts_for(cfg6, "ebitda")
    assert accounts == {"4000", "4001", "5000", "6000", "6001"}


def test_filters_narrow_results(cfg6):
    res = query_gl_detail(
        _repo(), cfg6,
        GLQuery(reporting_line="cogs", period=6, scenario="current_year", filters={"label": "late_booking"}),
    )
    assert len(res.rows) == 1
    assert "late_booking" in res.rows[0].labels


def test_canonical_row_order(cfg6):
    res = query_gl_detail(_repo(), cfg6, GLQuery(reporting_line="revenue", period=3, scenario="prior_year"))
    ids = [r.transaction_id for r in res.rows]
    assert ids == sorted(ids)
