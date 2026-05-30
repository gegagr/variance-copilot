"""Excel export (imperative shell — I/O).

Writes STRICTLY from a :class:`PnLResult`: line order, subtotal rows, and margin
rows come from the result's structure, and every numeric cell is the Decimal already
in the result. The exporter performs NO recomputation — the result is the single
source of figures (Constitution Principles I & VII).
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from engine.models import SCENARIO_ORDER, TIMECUT_ORDER, LineType, PnLResult

# Public so the parity test reads cells from the same coordinates the writer uses.
FIRST_DATA_ROW = 2
FIRST_VALUE_COL = 2  # column A is the reporting line label


def column_headers() -> list[str]:
    """Ordered scenario x time-cut column headers (matches cell layout)."""
    return [
        f"{scenario.value} / {time_cut.value}"
        for scenario in SCENARIO_ORDER
        for time_cut in TIMECUT_ORDER
    ]


def write_pnl(result: PnLResult, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "P&L"

    # Header row.
    ws.cell(row=1, column=1, value="Reporting Line").font = Font(bold=True)
    for offset, header in enumerate(column_headers()):
        ws.cell(row=1, column=FIRST_VALUE_COL + offset, value=header).font = Font(bold=True)

    # One row per reporting line, in canonical order.
    for r_offset, line in enumerate(result.lines):
        row = FIRST_DATA_ROW + r_offset
        label_cell = ws.cell(row=row, column=1, value=line.reporting_line)
        if line.line_type in (LineType.SUBTOTAL, LineType.MARGIN):
            label_cell.font = Font(bold=True)
        for c_offset, cell in enumerate(line.cells):
            target = ws.cell(row=row, column=FIRST_VALUE_COL + c_offset)
            target.value = float(cell.value)  # numeric for leadership readability
            if cell.is_margin:
                target.number_format = "0.0%"
            else:
                target.number_format = "#,##0.00"

    wb.save(path)
    return path
