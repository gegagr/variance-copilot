# Variance Copilot — Agent Context

AI-assisted P&L variance review tool for finance controllers. A deterministic engine
computes every number; a later AI layer investigates and drafts commentary. All work is
governed by the project constitution at `.specify/memory/constitution.md` (Determinism
First, Auditability, LLM Scope, Human in the Loop, Config-Driven, Source-Agnostic, Excel/
Word first-class, No Real Client Data).

## Active plan

<!-- SPECKIT START -->
- **002 — AI Investigation and Commentary Layer (Block 3)** *(active)*: [specs/002-ai-investigation-commentary/plan.md](specs/002-ai-investigation-commentary/plan.md)
  - Spec: [specs/002-ai-investigation-commentary/spec.md](specs/002-ai-investigation-commentary/spec.md)
  - Research: [specs/002-ai-investigation-commentary/research.md](specs/002-ai-investigation-commentary/research.md)
  - Data model: [specs/002-ai-investigation-commentary/data-model.md](specs/002-ai-investigation-commentary/data-model.md)
  - Contracts: [specs/002-ai-investigation-commentary/contracts/](specs/002-ai-investigation-commentary/contracts/)
  - Quickstart: [specs/002-ai-investigation-commentary/quickstart.md](specs/002-ai-investigation-commentary/quickstart.md)
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
