# Variance Copilot — Agent Context

AI-assisted P&L variance review tool for finance controllers. A deterministic engine
computes every number; a later AI layer investigates and drafts commentary. All work is
governed by the project constitution at `.specify/memory/constitution.md` (Determinism
First, Auditability, LLM Scope, Human in the Loop, Config-Driven, Source-Agnostic, Excel/
Word first-class, No Real Client Data).

## Active plan

<!-- SPECKIT START -->
- **001 — Deterministic P&L and Variance Engine (Block 1)**: [specs/001-pnl-variance-engine/plan.md](specs/001-pnl-variance-engine/plan.md)
  - Spec: [specs/001-pnl-variance-engine/spec.md](specs/001-pnl-variance-engine/spec.md)
  - Research: [specs/001-pnl-variance-engine/research.md](specs/001-pnl-variance-engine/research.md)
  - Data model: [specs/001-pnl-variance-engine/data-model.md](specs/001-pnl-variance-engine/data-model.md)
  - Contracts: [specs/001-pnl-variance-engine/contracts/](specs/001-pnl-variance-engine/contracts/)
  - Quickstart: [specs/001-pnl-variance-engine/quickstart.md](specs/001-pnl-variance-engine/quickstart.md)
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
