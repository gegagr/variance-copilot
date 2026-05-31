# Variance Copilot — Agent Context

AI-assisted P&L variance review tool for finance controllers. A deterministic engine
computes every number; a later AI layer investigates and drafts commentary. All work is
governed by the project constitution at `.specify/memory/constitution.md` (Determinism
First, Auditability, LLM Scope, Human in the Loop, Config-Driven, Source-Agnostic, Excel/
Word first-class, No Real Client Data).

## Active plan

<!-- SPECKIT START -->
- **005 — As-of Period Selector** *(active)*: [specs/005-as-of-period-selector/plan.md](specs/005-as-of-period-selector/plan.md)
  - Spec: [specs/005-as-of-period-selector/spec.md](specs/005-as-of-period-selector/spec.md)
  - Research: [specs/005-as-of-period-selector/research.md](specs/005-as-of-period-selector/research.md)
  - Data model: [specs/005-as-of-period-selector/data-model.md](specs/005-as-of-period-selector/data-model.md)
  - Contracts: [specs/005-as-of-period-selector/contracts/](specs/005-as-of-period-selector/contracts/)
  - Quickstart: [specs/005-as-of-period-selector/quickstart.md](specs/005-as-of-period-selector/quickstart.md)
- **004 — Review Workspace UI (Block 5)** *(implemented)*: [specs/004-review-workspace-ui/plan.md](specs/004-review-workspace-ui/plan.md)
- **003 — Review API Layer (Block 4)** *(implemented)*: [specs/003-review-api/plan.md](specs/003-review-api/plan.md)
- **002 — AI Investigation and Commentary Layer (Block 3)** *(implemented)*: [specs/002-ai-investigation-commentary/plan.md](specs/002-ai-investigation-commentary/plan.md)
- **001 — Deterministic P&L and Variance Engine (Block 1)** *(implemented)*: [specs/001-pnl-variance-engine/plan.md](specs/001-pnl-variance-engine/plan.md)
<!-- SPECKIT END -->

## Tech stack (Block 1)

- Python 3.12+, managed with `uv`.
- pandas (grouping/transform only — never for stored figures), Pydantic v2 (config +
  output models), openpyxl (Excel export), pytest.
- `decimal.Decimal` for ALL money/ratios. No float for stored financial figures.

## Architecture

Functional core / imperative shell. `engine/` is pure (no I/O, no network, no LLM).
The shell (`config/loader.py`, `data/fixture_repository.py`, `export/excel.py`,
`shell/pipeline.py`) does all I/O. Dependency direction is strictly shell → engine.
Data access is behind the abstract `Repository` (only `FixtureRepository` in Block 1).

## Non-negotiables when writing code here

- Determinism: explicit canonical ordering on every groupby/sort (stable `mergesort`);
  output must be byte-identical across runs. `current_period` is an input, never the clock.
- Reconciliation: subtotals == Σ components; margins == numerator/base; exact to the cent.
- Config-driven: all P&L structure in `config/*.csv`; no business structure in code.
- `FlaggedVariance` is the versioned public contract (`schema_version="1.0.0"`) — do not
  change its shape without bumping the version and the JSON Schema.
- Mock data only; real inputs stay git-ignored.

## Block 3 (agent layer) non-negotiables

- The LLM emits **no digits**. It references figures/evidence by id and emits placeholders;
  deterministic code in `agent/commentary.py` renders every number (verbatim source value or a
  code-computed aggregate over cited rows). `agent/guards.py` rejects any stray number.
- Ports-and-adapters: the agent core depends only on injected ports (`LLMProvider`,
  `query_gl_detail`) and contains zero SDK/HTTP calls. `OpenRouterProvider` is the only
  `httpx`/API-key site. All tests use `FakeLLMProvider` — no network in the suite.
- API key via `OPENROUTER_API_KEY` env var only — never committed, never written to the audit log.
- All output is a proposal; accept/edit/dismiss and report assembly are out of scope.

## Block 4 (review API) non-negotiables

- The API computes **no financial figure** — engine/agent objects pass through verbatim. Route
  handlers are thin; workflow logic lives in `api/services/`, never in routes; financial logic
  lives nowhere in this layer.
- Hexagonal: FastAPI driving adapter → `ReviewService` → engine/agent/`ReviewStore` ports. The
  service never imports FastAPI; the `ReviewStore` port has a SQLite/SQLAlchemy adapter.
- Lifecycle is an explicit state machine (`api/services/lifecycle.py`): invalid transitions are
  rejected (HTTP 409), never silently allowed. Nothing is final unless `status == accepted`;
  editing an accepted item reverts it to `drafted` (re-accept required), retaining the original.
- Every state change appends a `ReviewAction` (actor + timestamp). The SQLite review DB is
  config-driven and git-ignored. Tests run offline via `TestClient` + Block 3's `FakeLLMProvider`.

## Block 5 (web UI, `web/`) non-negotiables

- React + TypeScript SPA (Vite) consuming Block 4 only. The UI **computes no financial figure** — it
  renders the API's deterministic **display string** per figure verbatim; `lib/format.ts` is
  display-only and `noArithmetic.test.ts` fails the build on figure arithmetic.
- TanStack Query owns server state; mutations invalidate + refetch so card status always mirrors the
  API. Local React state holds only UI concerns (selected variance for anchoring, time cut).
- Types are **generated** from FastAPI `/openapi.json` (never hand-edited). All network access goes
  through the one typed `api/client.ts`. The OpenRouter key stays on the backend — the frontend
  never sees it and never calls the model.
- Visual: light surfaces, single indigo accent, semantic variance/status colors, Inter with tabular
  figures. Not a terminal — no monospace for content, no dark console theme.
- Dependency: Block 4 must serve a per-figure display string (`engine/format.py` + `*View` DTOs).
