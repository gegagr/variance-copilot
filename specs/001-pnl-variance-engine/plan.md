# Implementation Plan: Deterministic P&L and Variance Engine (Block 1)

**Branch**: `001-pnl-variance-engine` | **Date**: 2026-05-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-pnl-variance-engine/spec.md`

## Summary

Block 1 is the deterministic computational core of Variance Copilot. It ingests
transaction-level financial data through a `Repository` interface, maps GL accounts to
reporting lines, aggregates a configurable management P&L across three scenarios and
four time cuts (including the labeled current-year landing), computes variances
(absolute, percentage, percentage-point), flags material variances against configurable
thresholds, and exports the P&L to Excel.

Technical approach: a **functional core / imperative shell** split. The core (`engine/`)
is pure — deterministic functions over validated inputs returning Pydantic result
models, with no I/O and no network. A thin shell (`config/loader.py`,
`data/fixture_repository.py`, `export/excel.py`, `shell/pipeline.py`) performs all I/O.
All money is exact `Decimal`; every aggregation and sort uses explicit canonical
ordering so output is byte-identical across runs. No LLM and no network call appears
anywhere in this block.

## Technical Context

**Language/Version**: Python 3.12+, managed with `uv`

**Primary Dependencies**: pandas (aggregation/transformation), Pydantic v2 (config
validation + output models), openpyxl (Excel export). pytest (tests). Standard-library
`decimal.Decimal` for all monetary arithmetic.

**Storage**: Committed mock CSV under `sample/` (transactions) and `config/` (the five
config files). No database in this block; Supabase/real-CSV connectors are Block 2.

**Testing**: pytest — reconciliation suite, determinism/snapshot suite, edge-case suite.

**Target Platform**: Local/CLI library (offline). Importable pure-Python package.

**Project Type**: Single Python project (library + thin CLI/pipeline shell).

**Performance Goals**: Not latency-bound. Target: build the full scenario × time-cut P&L
for a realistic mock dataset (≈10k–50k transactions) in under a few seconds. Correctness
and determinism dominate; performance is secondary.

**Constraints**: Determinism is absolute — identical inputs + config produce
byte-identical output. Exact decimal arithmetic only (no float for stored figures). No
LLM, no network, no side effects in `engine/`. Reconciliation must hold to the cent.

**Scale/Scope**: Single reporting currency (EUR, label only). 3 scenarios × 4 time cuts.
Mock data only. Five config files. One Excel export.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | How this plan complies | Status |
|---|-----------|------------------------|--------|
| I | Determinism First | Pure `engine/` core; every figure from a Python function; `Decimal` arithmetic; canonical ordering on all groupby/sort; snapshot test enforces byte-identical output. No LLM in this block. | ✅ PASS |
| II | Auditability | Each P&L cell carries a provenance index of contributing transaction ids; each `FlaggedVariance` records the named rule id, thresholds, underlying values, and computed variance. Reconciliation status records any residual. | ✅ PASS |
| III | LLM Scope (investigate-and-draft only) | No LLM, no `query_gl_detail`, no agent in Block 1. Nothing to violate. | ✅ N/A |
| IV | Human in the Loop | No commentary or publishing in Block 1. Engine emits data only. | ✅ N/A |
| V | Config-Driven, Not Hardcoded | P&L layout, COA mapping, business structure, entity/geography rollups, and thresholds all live in CSV config validated by Pydantic. No business structure in code. | ✅ PASS |
| VI | Source-Agnostic Data | Engine depends only on the abstract `Repository`. `FixtureRepository` is the sole impl in Block 1; CSV/Supabase are Block 2 behind the same signature. | ✅ PASS |
| VII | Excel & Word Export First-Class | Excel export designed in from the start; reads figures from `PnLResult` only (no recompute). Word is a later block. | ✅ PASS |
| VIII | No Real Client Data | `sample/` and `config/` hold mock data only; `.gitignore` excludes real inputs; reproducibility enforced by the determinism test. | ✅ PASS |

**Result**: PASS. No violations — Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-pnl-variance-engine/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (Repository + FlaggedVariance schema)
│   ├── repository.md
│   ├── flagged_variance.schema.json
│   └── flagged_variance.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
engine/                          # PURE functional core — no I/O, no network, no LLM
├── __init__.py
├── models.py                    # Transaction (input) + PnLCell, PnLLine, PnLResult,
│                                #   Variance, FlaggedVariance (versioned), ReconciliationStatus
├── periods.py                   # time-cut selection + landing (elapsed actual + remaining budget)
├── pnl.py                       # build_pnl(): map → aggregate → subtotals → margins
├── variance.py                  # compute_variances(): abs, %, pp; favorable/unfavorable
├── flagging.py                  # flag_variances(): abs AND % (value) / pp (margin)
└── ordering.py                  # canonical sort + Decimal helpers (determinism utilities)

config/                          # config SCHEMAS + the five config files
├── __init__.py
├── schemas.py                   # Pydantic v2 models for all five configs + EngineConfig bundle
├── loader.py                    # format-agnostic loader (IMPERATIVE SHELL — I/O)
├── coa_mapping.csv              # GL account → reporting line
├── business_structure.csv       # business-unit hierarchy
├── entities_geographies.csv     # entity → geography → rollup
├── pnl_layout.csv               # line order, subtotals + components, margins + base, line type
└── thresholds.csv               # materiality: absolute, percentage, percentage-point (+ reporting settings)

data/                            # repository pattern
├── __init__.py
├── repository.py                # Repository ABC — the contract the engine depends on
└── fixture_repository.py        # FixtureRepository → reads sample/*.csv (IMPERATIVE SHELL — I/O)

export/                          # Excel export (IMPERATIVE SHELL — I/O)
├── __init__.py
└── excel.py                     # openpyxl writer; figures sourced from PnLResult only

shell/                           # imperative composition root
├── __init__.py
└── pipeline.py                  # load config → repo.fetch → core → export

sample/                          # committed MOCK data only (no real client data)
├── transactions_prior_year.csv
├── transactions_current_year.csv
└── transactions_budget.csv

tests/
├── conftest.py                  # shared fixtures (load sample config + data once)
├── test_reconciliation.py       # subtotals = Σ components; margins = line/base; ties to source
├── test_determinism.py          # byte-identical output across repeated runs (snapshot)
├── test_variance.py             # abs/%/pp correctness; negative & zero comparator
├── test_flagging.py             # abs AND % (value) / pp (margin); flag fields complete
└── test_edge_cases.py           # unmapped GLs surfaced; empty periods; zero-base margins

pyproject.toml                   # uv-managed project + dependencies
.gitignore                       # excludes real inputs; allows sample/ + config/ mock data
README.md
```

**Structure Decision**: Single Python project using the functional-core/imperative-shell
pattern. Dependency direction is strictly **shell → engine** (and config schemas →
engine domain types): `engine/` imports nothing from `data/`, `export/`, `shell/`, or
`config/loader.py`. The `Repository` ABC lives in `data/` and returns `engine` domain
models (`Transaction`), so the core owns its input contract while remaining
source-agnostic. The app packages live at the repository root; the vendored `spec-kit/`
tooling is unrelated to the application and may be git-ignored.

## Complexity Tracking

> No constitution violations. No entries required.
