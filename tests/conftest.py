"""Shared pytest fixtures and builders for the engine test suites."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from config.loader import load_config
from config.schemas import (
    CoaMappingRow,
    EngineConfig,
    EntityGeographyRow,
    PnLLayoutRow,
    ReportingSettings,
    ThresholdRow,
)
from data.fixture_repository import FixtureRepository
from engine.flagging import flag_variances
from engine.models import LineType, Scenario, Transaction
from engine.pnl import build_pnl
from engine.variance import compute_variances

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
SAMPLE_DIR = ROOT / "sample"


@pytest.fixture
def transactions() -> list[Transaction]:
    return FixtureRepository(SAMPLE_DIR).get_transactions()


@pytest.fixture
def cfg6() -> EngineConfig:
    return load_config(CONFIG_DIR, current_period=6)


@pytest.fixture
def result6(transactions, cfg6):
    return build_pnl(transactions, cfg6)


@pytest.fixture
def variances6(result6, cfg6):
    return compute_variances(result6, cfg6)


@pytest.fixture
def flags6(variances6, cfg6):
    return flag_variances(variances6, cfg6)


def cells_by_key(result) -> dict:
    return {(c.reporting_line, c.scenario, c.time_cut): c for line in result.lines for c in line.cells}


# --------------------------------------------------------------------------- #
# Builders for edge-case tests (in-memory, no files).
# --------------------------------------------------------------------------- #
def minimal_config(current_period: int = 6) -> EngineConfig:
    """A tiny revenue/cogs P&L with a gross-margin line (base = revenue)."""
    layout = [
        PnLLayoutRow(reporting_line="revenue", order=1, line_type=LineType.REVENUE),
        PnLLayoutRow(reporting_line="cogs", order=2, line_type=LineType.COST),
        PnLLayoutRow(
            reporting_line="gross_profit", order=3, line_type=LineType.SUBTOTAL,
            components=["revenue", "cogs"],
        ),
        PnLLayoutRow(
            reporting_line="gross_margin_pct", order=4, line_type=LineType.MARGIN,
            margin_numerator="gross_profit", margin_base="revenue",
        ),
    ]
    return EngineConfig(
        coa=[
            CoaMappingRow(gl_account="R", reporting_line="revenue"),
            CoaMappingRow(gl_account="C", reporting_line="cogs"),
        ],
        business=[],
        entities=[EntityGeographyRow(entity="E1", geography="G", rollup="R")],
        layout=layout,
        thresholds=[
            ThresholdRow(rule_id="value", applies_to="value",
                         abs_threshold=Decimal("100"), pct_threshold=Decimal("0.05"),
                         pp_threshold=Decimal("0")),
            ThresholdRow(rule_id="margin", applies_to="margin",
                         abs_threshold=Decimal("0"), pct_threshold=Decimal("0"),
                         pp_threshold=Decimal("0.01")),
        ],
        settings=ReportingSettings(current_period=current_period),
    )


def tx(tid: str, gl: str, amount: str, period: int, scenario: Scenario) -> Transaction:
    return Transaction(
        transaction_id=tid, gl_account=gl, amount=Decimal(amount), period=period,
        scenario=scenario, entity="E1", business_unit="BU1",
    )


# --------------------------------------------------------------------------- #
# Block 3 (agent layer) fixtures.
# --------------------------------------------------------------------------- #
@pytest.fixture
def ebitda_flag(flags6):
    """A flagged DETAIL-line variance whose reporting line resolves to GL rows.

    (Named historically `ebitda_flag`; ebitda is now a subtotal and is never flagged, so this
    points at a representative flagged detail line — IT costs, which carries a real anomaly.)
    """
    return next(
        f for f in flags6
        if f.reporting_line == "it_costs" and f.time_cut.value == "ytd"
        and f.scenario_pair.value == "current_vs_prior_year"
    )


@pytest.fixture
def gl_tool6(cfg6):
    from data.gl_detail_repository import GLDetailRepository
    from agent.tools import make_gl_tool
    return make_gl_tool(GLDetailRepository(SAMPLE_DIR), cfg6)


@pytest.fixture
def agent_settings():
    from config.agent_settings import load_agent_settings
    return load_agent_settings(CONFIG_DIR)


@pytest.fixture
def audit():
    from agent.audit import AuditLog
    return AuditLog()


# --------------------------------------------------------------------------- #
# Block 4 (API) fixtures.
# --------------------------------------------------------------------------- #
def fake_draft_final(narrative="EBITDA reached {{fig:flag.current_value}}.", status="draft"):
    from agent.fakes import final
    return final({"status": status, "narrative": narrative, "aggregates": []})


def fake_query(flag, period=6, scenario="current_year"):
    from agent.fakes import tool_call
    return tool_call("query_gl_detail",
                     {"reporting_line": flag.reporting_line, "period": period, "scenario": scenario})


@pytest.fixture
def make_api_client():
    """Build a TestClient with the provider + store overridden (offline, deterministic)."""
    from fastapi.testclient import TestClient
    from api.main import create_app
    from api.deps import get_provider, get_review_store
    from data.review_store import InMemoryReviewStore

    clients = []

    def _make(provider, store=None):
        store = store or InMemoryReviewStore()
        app = create_app()
        app.dependency_overrides[get_provider] = lambda: provider
        app.dependency_overrides[get_review_store] = lambda: store
        client = TestClient(app)
        clients.append(client)
        return client, store

    yield _make
    for c in clients:
        c.close()
