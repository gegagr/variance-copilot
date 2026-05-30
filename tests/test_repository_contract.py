"""Contract tests for the Repository seam (Constitution Principle VI)."""

from __future__ import annotations

from engine.models import Scenario, Transaction
from engine.pnl import build_pnl


def test_returns_only_valid_transactions(transactions):
    assert transactions, "fixture repository returned no transactions"
    assert all(isinstance(t, Transaction) for t in transactions)
    assert all(1 <= t.period <= 12 for t in transactions)
    assert {t.scenario for t in transactions} == {
        Scenario.PRIOR_YEAR, Scenario.CURRENT_YEAR, Scenario.BUDGET
    }


def test_stable_across_calls():
    from tests.conftest import SAMPLE_DIR
    from data.fixture_repository import FixtureRepository

    repo = FixtureRepository(SAMPLE_DIR)
    first = repo.get_transactions()
    second = repo.get_transactions()
    assert [t.model_dump() for t in first] == [t.model_dump() for t in second]


def test_engine_depends_on_abstraction_not_impl(cfg6):
    """A hand-built test double satisfies the engine without any concrete repo."""
    from data.repository import Repository
    from decimal import Decimal

    class StubRepo(Repository):
        def get_transactions(self):
            return [
                Transaction(transaction_id="t1", gl_account="4000", amount=Decimal("100.00"),
                            period=1, scenario=Scenario.CURRENT_YEAR, entity="E1",
                            business_unit="BU1"),
            ]

    result = build_pnl(StubRepo().get_transactions(), cfg6)
    assert result.reconciliation.is_complete
