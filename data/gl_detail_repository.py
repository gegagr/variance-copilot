"""GLDetailRepository: enriched mock GL detail for Block 3 (imperative shell — I/O).

Reads committed mock rows (transaction id, account, amount, period, scenario, entity,
business unit, date, counterparty, labels) from `sample/gl_detail.csv`. The amounts and
ids match the Block 1 transaction fixtures so GL figures reconcile with Block 1 output.
No network, no DB.
"""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from agent.models import GLEvidenceRow

LABEL_SEP = ";"


class GLDetailRepository:
    def __init__(self, sample_dir: Path) -> None:
        self.path = Path(sample_dir) / "gl_detail.csv"

    def get_gl_rows(self) -> list[GLEvidenceRow]:
        rows: list[GLEvidenceRow] = []
        with self.path.open(newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                labels = [x for x in (r.get("labels") or "").split(LABEL_SEP) if x]
                rows.append(
                    GLEvidenceRow(
                        transaction_id=r["transaction_id"].strip(),
                        gl_account=r["gl_account"].strip(),
                        amount=Decimal(r["amount"].strip()),
                        period=int(r["period"].strip()),
                        scenario=r["scenario"].strip(),
                        date=r["date"].strip(),
                        project=(r.get("project") or "").strip() or None,
                        counterparty=(r.get("counterparty") or "").strip() or None,
                        labels=labels,
                    )
                )
        return rows
