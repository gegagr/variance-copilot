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

## Block 3 — AI investigation & commentary layer (`agent/`)

Turns Block 1's flags into explained commentary. Ports-and-adapters: the agent core depends
only on injected ports (`LLMProvider`, `query_gl_detail`) and contains **no SDK/HTTP calls**.

- **`agent/`** — `models.py` (versioned InvestigationRecord/Question/Draft), `provider.py`
  (LLMProvider port + OpenRouter adapter — the only `httpx`/key site), `tools.py`
  (`query_gl_detail`), `investigate.py` (loop), `commentary.py` (reference→render),
  `guards.py` (traceability guard), `audit.py` (JSON-lines log), `fakes.py` (offline tests).
- The LLM **emits no digits**: it references figures by token and deterministic code renders
  every number (verbatim source value or a code-computed aggregate). `guards.py` rejects any
  stray number. All output is a proposal; accept/edit/dismiss is out of scope.

Run live (needs `OPENROUTER_API_KEY`):

```bash
export OPENROUTER_API_KEY=sk-...
uv run python -m shell.investigate_pipeline --current-period 6 --out build/investigations.jsonl
```

The whole test suite runs offline with a `FakeLLMProvider` — no key, no network.

## Block 4 — Review API layer (`api/`)

The composition root: a thin FastAPI driving adapter over a pure `ReviewService` that wires the
fixture Repository + engine + agent + a SQLite-backed `ReviewStore`. It serves the P&L, flags, and
AI investigation records, and manages the controller's review workflow (investigate → answer →
accept / edit / dismiss).

- **`api/`** — `main.py` (app + composition root, CORS, `/docs`), `deps.py` (DI providers),
  `schemas.py` (DTOs reusing Block 1/3 contracts), `routes/` (thin handlers), `services/`
  (`review_service.py` workflow + `lifecycle.py` state machine).
- **`data/review_store.py`** + **`data/sqlite_review_store.py`** — `ReviewStore` port + SQLite
  adapter (review DB git-ignored).
- The API **computes no figure** — engine/agent output passes through verbatim; nothing is final
  unless `status == accepted`; editing an accepted item reverts to `drafted`; every action is
  audited. Invalid lifecycle transitions are rejected (HTTP 409).

Run (live needs `OPENROUTER_API_KEY`):

```bash
uv run uvicorn api.main:app --reload     # Swagger UI at http://localhost:8000/docs
```

All API tests run offline via `TestClient` + Block 3's `FakeLLMProvider` (no key, no network).

## Block 5 — Review workspace UI (`web/`)

A React + TypeScript SPA (Vite) consuming the Block 4 API. It **renders figures from the API and
computes none** — every number is the API's deterministic display string (formatted by Python in
`engine/format.py`, served from `/pnl/view` and `/variances/view`), rendered verbatim. Card status
always mirrors the API's review lifecycle; TanStack Query mutations invalidate + refetch.

```bash
cd web && npm install
npm run gen:api          # regenerate types from the FastAPI OpenAPI schema (see web/README.md)
npm test                 # Vitest + RTL + MSW — fully offline
npm run dev              # live: proxies /api -> the FastAPI backend (OpenRouter key stays backend-only)
```

A `noArithmetic` test fails the build if any component does figure arithmetic — the presentation-
layer analogue of Block 3's guard and Block 4's pass-through test. See [web/README.md](web/README.md).

## Guarantees (enforced by tests)

- **Deterministic** — identical inputs + config produce byte-identical output (`test_determinism.py`).
- **Reconciled** — subtotals = Σ components; margins = numerator/base; ties to source (`test_reconciliation.py`).
- **Auditable** — every cell traces to source transactions (`test_traceability.py`).
- **Pure core** — `engine/` performs no I/O and imports no LLM (`test_architecture.py`).
- **Versioned contract** — `FlaggedVariance` v1.0.0 validated against its JSON Schema (`test_contract_flagged_variance.py`).
