---

description: "Task list for Deterministic P&L and Variance Engine (Block 1)"
---

# Tasks: Deterministic P&L and Variance Engine (Block 1)

**Input**: Design documents from `specs/001-pnl-variance-engine/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: INCLUDED — the spec and constitution mandate reconciliation, determinism, and
edge-case test suites. Within each story, tests are written FIRST and must FAIL before
implementation.

**Organization**: Tasks are grouped by user story (P1–P5 from spec.md). The stories form a
computational pipeline (each builds on the prior), but every story is an independently
testable increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US5 (user-story phases only)
- All paths are repository-root relative.

## Path Conventions

Single Python project, functional-core/imperative-shell layout at repo root:
`engine/` (pure core), `config/`, `data/`, `export/`, `shell/`, `sample/`, `tests/`.
Dependency direction is strictly **shell → engine**; `engine/` contains no I/O.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and structure.

- [x] T001 Create the package structure (`engine/`, `config/`, `data/`, `export/`, `shell/`, `sample/`, `tests/`, each with `__init__.py` where applicable) per plan.md
- [x] T002 Initialize the uv project and write `pyproject.toml` (Python 3.12+, dependencies: pandas, pydantic>=2, openpyxl, pytest)
- [x] T003 [P] Create `.gitignore` that EXCLUDES real client inputs but ALLOWS committed mock data under `sample/` and `config/` (Principle VIII)
- [x] T004 [P] Configure ruff + pytest settings in `pyproject.toml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared domain types, config, data seam, and mock data that ALL user stories
depend on.

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

- [x] T005 Define canonical enums (`Scenario`, `TimeCut`, `LineType`, `ValueKind`, `ScenarioPair`) and the `Transaction` input model in `engine/models.py` per data-model.md
- [x] T006 [P] Implement Decimal helpers (quantize to money/ratio precision) and canonical-ordering utilities (stable `mergesort`, explicit sort keys) in `engine/ordering.py`
- [x] T007 [P] Define Pydantic v2 schemas for all five configs (`CoaMappingRow`, `BusinessUnitRow`, `EntityGeographyRow`, `PnLLayoutRow`, `ThresholdRow`), plus `ReportingSettings` and the `EngineConfig` bundle, in `config/schemas.py`
- [x] T008 Implement config validation in `config/schemas.py` — duplicate GL mapping, unknown/cyclic subtotal components, unknown margin numerator/base, unique `order` — raising explicit configuration errors (FR-024) (depends on T007)
- [x] T009 Implement the format-agnostic config loader with a `read_table()` indirection (CSV today) returning validated `EngineConfig` in `config/loader.py` (depends on T007, T008)
- [x] T010 [P] Define the abstract `Repository` interface (`get_transactions() -> list[Transaction]`) in `data/repository.py` per contracts/repository.md (depends on T005)
- [x] T011 Implement `FixtureRepository` reading `sample/*.csv` into validated `Transaction` objects (amounts → Decimal) in `data/fixture_repository.py` (depends on T010, T005)
- [x] T012 [P] Create mock config files: `config/coa_mapping.csv`, `config/business_structure.csv`, `config/entities_geographies.csv`, `config/pnl_layout.csv`, `config/thresholds.csv` (incl. reporting settings: currency EUR, precision, current_period)
- [x] T013 [P] Create mock transaction data: `sample/transactions_prior_year.csv`, `sample/transactions_current_year.csv`, `sample/transactions_budget.csv` (narratively coherent, multiple entities/BUs/periods)
- [x] T014 Add shared pytest fixtures (load sample config + data once) in `tests/conftest.py` and a Repository contract test (returns only valid `Transaction`s; stable across calls) in `tests/test_repository_contract.py` (depends on T009, T011, T012, T013)

**Checkpoint**: Domain types, config, repository, and mock data ready — user stories can begin.

---

## Phase 3: User Story 1 - Build the management P&L from transactions and config (Priority: P1) 🎯 MVP

**Goal**: Map GL accounts to reporting lines, aggregate an ordered P&L with subtotals and
margins for the scenario/time-cut grid's base path, reconcile to source, and surface
unmapped accounts.

**Independent Test**: Given a fixed transaction set + the five configs, the returned P&L
matches a hand-computed expected result line-for-line; every subtotal equals Σ its
components; every margin equals numerator/base; the total ties to source with zero residual
for fully-mapped data; unmapped accounts are surfaced (never dropped).

### Tests for User Story 1 ⚠️ (write first, must fail)

- [x] T015 [P] [US1] Reconciliation tests (subtotal == Σ components; margin == numerator/base; ties to source, zero residual on fully-mapped data) in `tests/test_reconciliation.py`
- [x] T016 [P] [US1] Edge-case tests (unmapped GLs surfaced with residual and `is_complete=False`; zero-base margin → `not_meaningful`, no crash) in `tests/test_edge_cases.py`

### Implementation for User Story 1

- [x] T017 [US1] Define P&L output models (`PnLCell`, `PnLLine`, `ReconciliationStatus`, `ProvenanceIndex`, `PnLResult`) in `engine/models.py` per data-model.md (depends on T005)
- [x] T018 [US1] Implement GL→reporting-line mapping with explicit unmapped-account surfacing + residual accumulation in `engine/pnl.py` (depends on T017, T007)
- [x] T019 [US1] Implement aggregation (Decimal sums over canonically-sorted groups), subtotals, margins, the provenance index, and `ReconciliationStatus` in `engine/pnl.py` (depends on T018, T006)
- [x] T020 [US1] Finalize `build_pnl(transactions, config) -> PnLResult` and make T015/T016 pass in `engine/pnl.py` (depends on T019)

**Checkpoint**: P&L builds and reconciles for the base grid — MVP is independently demoable.

---

## Phase 4: User Story 2 - Produce scenarios across time cuts, including the labeled landing (Priority: P2)

**Goal**: Populate every line for 3 scenarios × 4 time cuts, with the current-year
full-year column computed as a labeled landing (elapsed actual + remaining budget), never
conflated with true YTD actuals.

**Independent Test**: For a fixed dataset with known current period, YTD actuals and the
full-year landing appear as distinct, clearly named columns; landing == elapsed actuals +
remaining budget; landing carries the `landing` value-kind; empty periods yield defined
columns without failure.

### Tests for User Story 2 ⚠️ (write first, must fail)

- [x] T021 [P] [US2] Scenario/time-cut + landing tests (YTD ≠ landing; landing == Σ current-year actual[1..p] + Σ budget[p+1..12]; boundaries p=1 and p=12; empty period yields a defined column) in `tests/test_scenarios.py`

### Implementation for User Story 2

- [x] T022 [US2] Implement time-cut selection (prior-month YTD, current month, YTD, full year) and landing composition, with `current_period` as an explicit input, in `engine/periods.py` (depends on T005)
- [x] T023 [US2] Extend `build_pnl` to emit all 3 scenarios × 4 time cuts with correct `value_kind` tagging (actual/budget/landing) in `engine/pnl.py` (depends on T022, T020)
- [x] T024 [US2] Ensure provenance + reconciliation cover the full grid; make T021 pass in `engine/pnl.py` (depends on T023)
- [x] T040 [P] [US2] Traceability test (SC-005 / Constitution II): every leaf cell has a non-empty provenance set for non-empty periods, and subtotal/margin cells trace transitively to source `transaction_id`s, in `tests/test_traceability.py` (appended out-of-sequence to preserve existing IDs; US2-scoped)

**Checkpoint**: Full scenario × time-cut grid with labeled landing, independently testable.

---

## Phase 5: User Story 3 - Compute variances for every line (Priority: P3)

**Goal**: For every line, compute current-vs-prior-year and current-vs-budget variances
(absolute + percentage; percentage-points for margins), with favorable/unfavorable derived
from line type.

**Independent Test**: Absolute variance == current − comparator; percentage variance ==
(current − comparator)/|comparator| with zero comparator → not meaningful; margin variances
are percentage-point differences; direction matches line type.

### Tests for User Story 3 ⚠️ (write first, must fail)

- [x] T025 [P] [US3] Variance tests (abs/%/pp correctness; absolute-value denominator for negative comparator; zero comparator → `not_meaningful`; favorable/unfavorable by line type) in `tests/test_variance.py`

### Implementation for User Story 3

- [x] T026 [US3] Define the `Variance` model in `engine/models.py` per data-model.md (depends on T005)
- [x] T027 [US3] Implement `compute_variances(result, config) -> list[Variance]` (abs, %, pp; direction from `line_type`) in `engine/variance.py` (depends on T026, T023)

**Checkpoint**: Variances computed for the full grid, independently testable.

---

## Phase 6: User Story 4 - Flag material variances against configurable rules (Priority: P4)

**Goal**: Flag variances per configurable thresholds (value lines: absolute AND percentage;
margin lines: percentage-point), emitting the versioned `FlaggedVariance` public contract.

**Independent Test**: A value variance breaching BOTH abs and % is flagged; one breaching
only one is not; margin flags fire on pp; every flag carries line, time cut, scenario pair,
underlying values, computed variance, and the triggering rule; output validates against the
v1.0.0 JSON Schema.

### Tests for User Story 4 ⚠️ (write first, must fail)

- [x] T028 [P] [US4] Contract test: the live `FlaggedVariance` JSON Schema equals `contracts/flagged_variance.schema.json`; Decimal fields serialize as strings; `schema_version == "1.0.0"` in `tests/test_contract_flagged_variance.py`
- [x] T029 [P] [US4] Flagging tests (value flagged only on abs AND %; margin on pp; nothing below thresholds; all fields populated; deterministic `flag_id`) in `tests/test_flagging.py`

### Implementation for User Story 4

- [x] T030 [US4] Define the `FlaggedVariance` model with `schema_version: Literal["1.0.0"]` and Decimal-as-string serialization in `engine/models.py` (depends on T005)
- [x] T031 [US4] Implement `flag_variances(variances, config) -> list[FlaggedVariance]` with rule selection by category (`value` = revenue|cost|subtotal → abs-AND-%; `margin` → pp), and deterministic `flag_id` in `engine/flagging.py` (depends on T030, T027)
- [x] T032 [US4] Add a schema-export sync step keeping `contracts/flagged_variance.schema.json` in lockstep with the model; make T028/T029 pass (depends on T031)

**Checkpoint**: Flagging works and the public contract is drift-protected, independently testable.

---

## Phase 7: User Story 5 - Export the P&L to Excel (Priority: P5)

**Goal**: Export the P&L to Excel preserving line hierarchy, subtotals, and margins, with
figures identical to the in-memory `PnLResult`.

**Independent Test**: Export a known P&L and confirm the workbook preserves line order,
subtotal rows, and margin rows, with every figure equal to the corresponding `PnLResult`
value (no rounding/recompute).

### Tests for User Story 5 ⚠️ (write first, must fail)

- [x] T033 [P] [US5] Excel parity test (round-trip workbook equals `PnLResult` figures; line order, subtotals, margins preserved) in `tests/test_excel_export.py`

### Implementation for User Story 5

- [x] T034 [US5] Implement the openpyxl exporter writing STRICTLY from `PnLResult` (no recomputation) in `export/excel.py` (depends on T019, T023)

**Checkpoint**: Excel export parity verified, independently testable.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Determinism guarantee, end-to-end wiring, and architecture/quality guards.

- [x] T035 [P] Determinism/snapshot test: full grid + flags are byte-identical across repeated runs and across input permutations (after canonical sort) in `tests/test_determinism.py`
- [x] T036 Implement the imperative composition root `shell/pipeline.py` (load config → `FixtureRepository` → `build_pnl` → `compute_variances` → `flag_variances` → write `pnl.xlsx` + `flags.json`) with a `--current-period` CLI arg (depends on T020, T023, T027, T031, T034)
- [x] T037 [P] Architecture guard test: `engine/` imports no I/O (`open`, `pandas.read_*`, `openpyxl`, `requests`, network) and no LLM in `tests/test_architecture.py`
- [x] T038 [P] Write `README.md` and validate every command in `quickstart.md` runs end-to-end
- [x] T039 [P] Final docstrings and a Success-Criteria traceability note mapping SC-001…SC-010 to their covering tests in `tests/README.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories.
- **User Stories (Phases 3–7)**: all depend on Foundational. The stories form a pipeline:
  US1 → US2 → US3 → US4, with US5 depending on US1/US2. Each is an independently testable
  increment, but later compute stories build on earlier outputs (not fully parallel).
- **Polish (Phase 8)**: depends on the relevant user stories being complete.

### User Story Dependencies

- **US1 (P1)**: after Foundational. No dependency on other stories. (MVP)
- **US2 (P2)**: extends US1's `build_pnl` (depends on US1).
- **US3 (P3)**: consumes US2's full grid (depends on US2).
- **US4 (P4)**: consumes US3's variances (depends on US3).
- **US5 (P5)**: consumes US1/US2's `PnLResult` (depends on US2; can proceed in parallel with US3/US4).

### Within Each User Story

- Tests written first and FAIL before implementation.
- Models before the functions that use them.
- Core (engine) before shell/export integration.

### Parallel Opportunities

- Setup: T003, T004 in parallel.
- Foundational: T006, T007, T010, T012, T013 in parallel (different files); T008/T009 after T007; T011 after T010; T014 last.
- Within a story, the `[P]` test tasks run together (separate files).
- US5 (T033–T034) can run in parallel with US3/US4 once US2 is done (different files: `export/`, `tests/test_excel_export.py`).
- Polish: T035, T037, T038, T039 in parallel; T036 after its dependencies.

---

## Parallel Example: Foundational Phase

```bash
# After T005, launch these together (different files):
Task: "Implement Decimal + ordering helpers in engine/ordering.py"          # T006
Task: "Define Pydantic config schemas in config/schemas.py"                  # T007
Task: "Define Repository ABC in data/repository.py"                          # T010
Task: "Create mock config CSVs in config/*.csv"                              # T012
Task: "Create mock transaction CSVs in sample/*.csv"                         # T013
```

## Parallel Example: User Story 1 tests

```bash
Task: "Reconciliation tests in tests/test_reconciliation.py"                 # T015
Task: "Edge-case tests in tests/test_edge_cases.py"                          # T016
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational (CRITICAL — blocks all stories) →
3. Phase 3 US1 → 4. **STOP and VALIDATE**: P&L builds, reconciles, surfaces unmapped accounts.
   This alone replaces a manual mapping-and-aggregation spreadsheet.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → reconciling P&L (MVP).
3. US2 → full scenario × time-cut grid with labeled landing.
4. US3 → variances.
5. US4 → material flags + versioned public contract.
6. US5 → Excel export (parallelizable with US3/US4).
7. Polish → determinism guarantee + end-to-end pipeline.

Each increment is independently testable and adds value without breaking the prior.

---

## Notes

- `[P]` = different files, no incomplete dependencies. Tasks touching `engine/models.py`
  (T005, T017, T026, T030) share a file and are intentionally NOT marked `[P]`.
- Tests precede implementation within each story and must fail first.
- Constitution guards: T035 (determinism), T037 (no I/O / no LLM in core), T032 (contract
  drift), T015 (reconciliation) are the non-negotiable gates.
- Commit after each task or logical group; stop at any checkpoint to validate independently.
