"""FixtureRepository: the only Repository implementation in Block 1 (imperative shell).

Reads committed MOCK CSV from a ``sample/`` directory. One file per scenario; the
scenario is assigned from the filename so the CSVs stay minimal. No network, no DB.
"""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from data.repository import Repository
from engine.models import Scenario, Transaction

_SCENARIO_FILES: dict[Scenario, str] = {
    Scenario.PRIOR_YEAR: "transactions_prior_year.csv",
    Scenario.CURRENT_YEAR: "transactions_current_year.csv",
    Scenario.BUDGET: "transactions_budget.csv",
}


class FixtureRepository(Repository):
    def __init__(self, sample_dir: Path) -> None:
        self.sample_dir = Path(sample_dir)

    def get_transactions(self) -> list[Transaction]:
        transactions: list[Transaction] = []
        for scenario, filename in _SCENARIO_FILES.items():
            path = self.sample_dir / filename
            if not path.exists():
                continue
            with path.open(newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    transactions.append(
                        Transaction(
                            transaction_id=row["transaction_id"].strip(),
                            gl_account=row["gl_account"].strip(),
                            amount=Decimal(row["amount"].strip()),
                            period=int(row["period"].strip()),
                            scenario=scenario,
                            entity=row["entity"].strip(),
                            business_unit=row["business_unit"].strip(),
                            project=(row.get("project") or "").strip() or None,
                        )
                    )
        return transactions
