# Quickstart: Deterministic P&L and Variance Engine (Block 1)

This block is a pure-Python library plus a thin I/O shell. No network, no LLM.

## Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)

## Setup

```bash
uv sync                 # create venv + install pinned deps (pandas, pydantic v2, openpyxl, pytest)
```

## Run the engine end-to-end (shell pipeline)

```bash
uv run python -m shell.pipeline \
  --config-dir config \
  --sample-dir sample \
  --current-period 6 \
  --out build/pnl.xlsx
```

This wires the imperative shell:

1. `config/loader.py` loads + validates the five config files → `EngineConfig`.
2. `FixtureRepository(sample/)` returns `list[Transaction]`.
3. Pure core: `build_pnl` → `compute_variances` → `flag_variances`.
4. `export/excel.py` writes `build/pnl.xlsx` (figures sourced from `PnLResult` only).
5. Flagged variances are written to `build/flags.json` (validates against the v1.0.0
   contract).

## Use the pure core directly (no I/O)

```python
from engine.pnl import build_pnl
from engine.variance import compute_variances
from engine.flagging import flag_variances

result = build_pnl(transactions, config)        # transactions + config are plain objects
variances = compute_variances(result, config)
flags = flag_variances(variances, config)

assert result.reconciliation.is_complete         # for a fully-mapped dataset
```

The core takes already-validated inputs and returns Pydantic models — trivially testable.

## Run the tests

```bash
uv run pytest                      # all suites
uv run pytest tests/test_reconciliation.py
uv run pytest tests/test_determinism.py
```

Test suites:

- **Reconciliation** — subtotals = Σ components; margins = numerator/base; ties to source
  with zero residual on fully-mapped data.
- **Determinism/snapshot** — identical inputs + config produce byte-identical output across
  repeated runs and input permutations.
- **Variance** — abs/%/pp correctness; negative comparator uses `abs()`; zero comparator →
  not meaningful.
- **Flagging** — value lines flag on abs AND %; margins on pp; all flag fields populated.
- **Edge cases** — unmapped GLs surfaced (never dropped) with residual; empty periods;
  zero-base margins.

## Editing the P&L without touching code (Principle V)

- Re-map an account → edit `config/coa_mapping.csv`.
- Re-order lines / change a subtotal's components / change a margin's base → edit
  `config/pnl_layout.csv`.
- Change materiality → edit `config/thresholds.csv`.

No Python change is required; re-run the pipeline.

## Data & safety

- `sample/` and `config/` contain **mock data only**.
- `.gitignore` excludes real client inputs; never commit real data (Principle VIII).
