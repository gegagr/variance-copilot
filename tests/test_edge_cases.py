"""US1 edge-case tests: unmapped GL accounts and zero-base margins (FR-002, robustness)."""

from __future__ import annotations

from decimal import Decimal

from engine.models import Scenario, TimeCut, ValueKind
from engine.pnl import build_pnl
from tests.conftest import cells_by_key, minimal_config, tx


def test_unmapped_accounts_surfaced_not_dropped():
    cfg = minimal_config(current_period=1)
    txns = [
        tx("t1", "R", "1000.00", 1, Scenario.CURRENT_YEAR),   # mapped revenue
        tx("t2", "C", "-400.00", 1, Scenario.CURRENT_YEAR),   # mapped cogs
        tx("t3", "9999", "250.00", 1, Scenario.CURRENT_YEAR), # UNMAPPED
    ]
    result = build_pnl(txns, cfg)

    # P&L is still built from mapped transactions.
    cells = cells_by_key(result)
    assert cells[("revenue", Scenario.CURRENT_YEAR, TimeCut.CURRENT_MONTH)].value == Decimal("1000.00")

    # But the run is marked incomplete with the unmapped amount as residual.
    assert result.reconciliation.is_complete is False
    assert result.reconciliation.residual == Decimal("250.00")
    assert result.reconciliation.unmapped_accounts == {"9999": Decimal("250.00")}


def test_fully_mapped_dataset_is_complete():
    cfg = minimal_config(current_period=1)
    txns = [tx("t1", "R", "1000.00", 1, Scenario.CURRENT_YEAR)]
    result = build_pnl(txns, cfg)
    assert result.reconciliation.is_complete is True
    assert result.reconciliation.unmapped_accounts == {}


def test_zero_base_margin_marked_not_meaningful():
    """Revenue is zero, so gross_margin (base = revenue) must not crash."""
    cfg = minimal_config(current_period=1)
    txns = [tx("t1", "C", "-400.00", 1, Scenario.CURRENT_YEAR)]  # cost only, no revenue
    result = build_pnl(txns, cfg)
    cells = cells_by_key(result)
    margin = cells[("gross_margin_pct", Scenario.CURRENT_YEAR, TimeCut.CURRENT_MONTH)]
    assert margin.value_kind is ValueKind.NOT_MEANINGFUL
    assert margin.value == Decimal("0")
