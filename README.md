# Variance Copilot — Deterministic P&L & Variance Engine (Block 1)

The deterministic computational core of Variance Copilot. It turns transaction-level
financial data into a configurable management P&L, computes variances across scenarios
and time periods, flags material variances, and exports to Excel. **No LLM and no network
calls anywhere in this block** — every figure is produced by deterministic Python.

See the governing principles in [`.specify/memory/constitution.md`](.specify/memory/constitution.md)
and the feature docs in [`specs/001-pnl-variance-engine/`](specs/001-pnl-variance-engine/).

## Architecture

Functional core / imperative shell:

- **`engine/`** — pure core (no I/O, no network, no LLM). `pnl.py`, `variance.py`,
  `flagging.py`, `periods.py`, `ordering.py`, `models.py`. All money/ratios are `Decimal`.
- **`config/`** — Pydantic config schemas (`schemas.py`), the format-agnostic loader
  (`loader.py`), and the five CSV config files.
- **`data/`** — the `Repository` abstraction and `FixtureRepository` (reads `sample/`).
- **`export/`** — openpyxl Excel writer (writes strictly from the P&L result).
- **`shell/`** — `pipeline.py`, the imperative composition root.
- **`sample/`** — committed **mock** transaction data (no real client data, ever).

Dependency direction is strictly **shell → engine**; the engine never performs I/O.

## Quickstart

```bash
uv sync
uv run python -m shell.pipeline --config-dir config --sample-dir sample \
    --current-period 6 --out build/pnl.xlsx
uv run pytest
```

This produces `build/pnl.xlsx` and `build/flags.json`. See
[`specs/001-pnl-variance-engine/quickstart.md`](specs/001-pnl-variance-engine/quickstart.md)
for details.

## Editing the P&L without touching code

All structure lives in `config/*.csv` (Constitution Principle V):

- `coa_mapping.csv` — GL account → reporting line
- `pnl_layout.csv` — line order, subtotals + components, margins + base, line type
- `business_structure.csv`, `entities_geographies.csv` — hierarchy & rollups
- `thresholds.csv` — materiality (absolute / percentage / percentage-point)
- `reporting_settings.csv` — currency (EUR), precision, current period, sign convention

Re-run the pipeline; no Python change required.

## Guarantees (enforced by tests)

- **Deterministic** — identical inputs + config produce byte-identical output (`test_determinism.py`).
- **Reconciled** — subtotals = Σ components; margins = numerator/base; ties to source (`test_reconciliation.py`).
- **Auditable** — every cell traces to source transactions (`test_traceability.py`).
- **Pure core** — `engine/` performs no I/O and imports no LLM (`test_architecture.py`).
- **Versioned contract** — `FlaggedVariance` v1.0.0 validated against its JSON Schema (`test_contract_flagged_variance.py`).
