# Phase 0 Research: Deterministic P&L and Variance Engine

All decisions below resolve the "NEEDS CLARIFICATION" space of the Technical Context.
There were no open clarifications from the spec (the four clarify-session decisions are
already encoded). The research focuses on *how* to satisfy Determinism First and
Auditability with the chosen stack.

---

## R1. Exact decimal money with pandas

**Decision**: Represent every monetary amount as `decimal.Decimal`, quantized to a
config-declared precision (default 2 dp = cents). Load amounts into `Decimal` at the
shell boundary (config/data loaders). Use pandas for **grouping, filtering, and joining
only**; perform all summation as a deterministic `Decimal` reduction over sorted groups.
Margins and ratios are `Decimal` divisions quantized to a config-declared ratio
precision (default 6 dp) before storage; display rounding is separate.

**Rationale**: pandas/NumPy default to `float64`, which violates Determinism First and
breaks exact reconciliation (subtotal = Σ components to the cent). Holding money as
`Decimal` in `object`-dtype columns keeps exactness; pandas still provides ergonomic
groupby/join. Summing sorted `Decimal` sequences is associative and reproducible.

**Alternatives considered**:
- *Integer minor units (cents as int)*: exact and fast, but awkward for ratios/margins
  and for multi-precision configs; rejected for ergonomics, kept as a fallback option.
- *float64 + rounding tolerance*: rejected outright — violates the constitution and the
  Q2 clarification (exact decimal, no tolerance).

## R2. Deterministic aggregation & ordering with pandas

**Decision**: Every `groupby` uses `sort=True` and is followed by an explicit
`sort_values` with a fully-specified key list and `kind="mergesort"` (stable). Reporting
lines are ordered by the `order` column in `pnl_layout.csv`; scenarios and time cuts use
fixed enum orderings defined in `engine/ordering.py`. Transactions are canonicalized to a
stable sort (entity, business_unit, gl_account, period, amount, then a tie-break id)
before any reduction. No code relies on dict insertion order, set iteration order, or
default unstable sorts.

**Rationale**: Byte-identical output (SC-001, determinism test) requires that ordering be
a function of the data and config, never of incidental insertion/hash order.
`mergesort` is the only stable sort kind pandas exposes.

**Alternatives considered**: Relying on pandas' default `quicksort` — rejected (unstable,
non-reproducible tie ordering).

## R3. Time cuts and the landing estimate

**Decision**: Model the fiscal year as 12 ordinal periods (months) `1..12`. The current
period `p` is an explicit input to the engine (not derived from a wall clock — preserves
determinism). Definitions:
- **Current month** = period == `p`.
- **YTD** = periods `1..p` (true actuals for the current-year scenario).
- **Prior-month YTD** = periods `1..(p-1)` (empty when `p == 1`).
- **Full year**: for prior-year and budget scenarios = periods `1..12`. For the
  **current-year** scenario = the **landing** = current-year actuals for periods `1..p`
  **plus** budget for periods `(p+1)..12`. The landing cell is tagged
  `value_kind="landing"`; YTD actual cells are tagged `value_kind="actual"`; they are
  never merged (FR-008, FR-009).

**Rationale**: Passing `current_period` as input makes the YTD/landing split a pure
function of inputs (Determinism First) and makes boundary cases (`p==1`, `p==12`)
testable. Tagging value kind enforces the actual-vs-landing separation in the type system.

**Alternatives considered**: Deriving the current period from `date.today()` — rejected,
non-deterministic and untestable.

## R4. Percentage, percentage-point, and favorable/unfavorable semantics

**Decision** (encodes Q3 clarification):
- Absolute variance = `current - comparator` (signed `Decimal`).
- Percentage variance = `(current - comparator) / abs(comparator)`, quantized; when
  `comparator == 0` → marked `not_meaningful` (no division).
- Margin lines: variance is **percentage points** = `margin_current - margin_comparator`
  (a `Decimal` difference of two ratios), never a percentage of a percentage.
- Favorable/unfavorable is derived from the reporting line's `line_type`
  (`revenue` vs `cost`) declared in `pnl_layout.csv`, not from the raw sign: a positive
  delta on a revenue line is favorable; a positive delta on a cost line is unfavorable.

**Rationale**: Direct from the spec (FR-010, FR-011, FR-012, FR-013) and the clarify
session. Absolute-value denominator keeps percentages intuitive for negative bases.

**Alternatives considered**: Signed denominator (sign-flips on negative bases) and
always-positive magnitude (loses signed %) — both rejected in the clarify session.

## R5. Flagging logic

**Decision** (encodes Q1 clarification): For a **value** (non-margin) line, emit a flag
only when the absolute variance breaches the absolute threshold **AND** the percentage
variance breaches the percentage threshold (de-minimis guard). For a **margin** line,
emit a flag when the percentage-point variance breaches the pp threshold. Thresholds come
from `thresholds.csv`; the applicable rule is selected by rule category — `value`
(revenue | cost | subtotal) → abs-AND-% rule, `margin` → pp rule. Each flag records the
named rule id, all three threshold values, the scenario pair, time cut, underlying values,
and computed variance.

**Rationale**: Direct from FR-015 and the clarify session. Selecting the rule by line type
keeps the combination logic derivable from config + line type.

**Alternatives considered**: OR-any and abs-OR-% — rejected in the clarify session.

## R6. FlaggedVariance schema versioning (public contract)

**Decision**: `FlaggedVariance` is a Pydantic v2 model carrying an explicit
`schema_version: Literal["1.0.0"]` field. The JSON Schema is exported to
`contracts/flagged_variance.schema.json` and treated as the public contract for Block 3
(the AI layer). Any change to the shape bumps the version deliberately; a contract test
asserts the model serializes to the pinned schema.

**Rationale**: FR-017 requires a documented, versioned, stable public interface. Pinning a
literal version and snapshotting the JSON Schema makes drift a test failure, not a silent
break.

**Alternatives considered**: Implicit/unversioned dataclass — rejected (no drift
protection for the downstream contract).

## R7. Repository interface (source-agnostic seam)

**Decision**: An abstract base class `Repository` in `data/repository.py` exposing a
single read method returning all transactions as validated `engine` domain models:

```python
class Repository(ABC):
    @abstractmethod
    def get_transactions(self) -> list[Transaction]: ...
```

Each `Transaction` is tagged with `scenario` (prior_year | current_year | budget) and
`period` (1..12). The engine slices by scenario/period internally. `FixtureRepository`
reads the three `sample/*.csv` files. Block 2's CSV/Supabase repos implement the same ABC.

**Rationale**: VI (Source-Agnostic Data). A single, narrow read method keeps the engine
ignorant of the source. Returning domain models (not DataFrames) keeps the contract stable
across very different backends.

**Alternatives considered**: Per-scenario methods or returning DataFrames — rejected;
DataFrames would leak pandas into the contract and couple backends to a tabular shape.

## R8. Config loading, format-agnostic

**Decision**: `config/loader.py` reads CSV today but returns validated Pydantic models, so
the engine never sees raw files. A thin `read_table(path) -> list[dict]` indirection
isolates the file format, allowing an xlsx loader to be substituted later without touching
schemas or engine. Config validation (duplicate GL mappings, unknown base lines, cyclic
subtotals) happens in the Pydantic models / a post-load validator and raises explicit
configuration errors (FR-024).

**Rationale**: V (Config-Driven) and the spec's format-agnostic requirement. Validation at
load turns config mistakes into clear errors rather than silently wrong totals.

**Alternatives considered**: Parsing CSV inside the engine — rejected (I/O in the core
violates the architecture and Determinism testability).

## R9. Excel export parity

**Decision**: `export/excel.py` (openpyxl) writes strictly from a `PnLResult` object:
line order, subtotal rows, and margin rows come from the result's structure; every numeric
cell is the `Decimal` already in the result, written without recomputation. A parity test
reads the workbook back and asserts equality with the in-memory result (SC-010).

**Rationale**: VII (Excel first-class) and Determinism First — the exporter must not be a
second, divergent computation path. Single source of figures = `PnLResult`.

**Alternatives considered**: Re-aggregating inside the exporter — rejected (creates a
second numeric path that can diverge).

## R10. Auditability / traceability index

**Decision**: `build_pnl` produces, alongside the P&L, a provenance index mapping each
leaf (non-subtotal) cell `(reporting_line, scenario, time_cut)` to the set of contributing
transaction ids. Subtotals trace transitively through their component lines; margins trace
through numerator and base. This satisfies "every figure traces to source transactions"
(FR-028, II) without bloating every cell — the index is a sibling structure on the result.

**Rationale**: II (Auditability). Keeping provenance as an index keeps `PnLCell` light
while still guaranteeing full traceability for 100% of cells (SC-005).

**Alternatives considered**: Embedding the full id list on every cell — rejected (heavy,
duplicative for subtotals). No provenance — rejected (violates II).

## R11. Reconciliation status & unmapped accounts

**Decision** (encodes Q4 clarification): `build_pnl` always returns a `PnLResult`
including a `ReconciliationStatus` with `is_complete: bool`, `residual: Decimal`
(= Σ unmapped amounts), and an `unmapped_accounts` report (account → amount). When
unmapped accounts exist the P&L is still built from mapped transactions and
`is_complete=False`. Exact reconciliation (subtotal/margin ties, zero residual) is
asserted by tests only on fully-mapped datasets (SC-002, SC-003).

**Rationale**: Q4 clarification + FR-002. Build-and-warn is usable yet honest; the residual
makes the gap explicit and auditable.

**Alternatives considered**: Hard-fail and catch-all line — rejected in the clarify
session.

## R12. Tooling: uv + pytest layout

**Decision**: `uv`-managed `pyproject.toml` pinning Python 3.12+, pandas, pydantic>=2,
openpyxl, pytest. Top-level importable packages (no `src/` layout) to match the requested
structure. Tests load the committed sample config + data via `conftest.py` fixtures.

**Rationale**: Matches the user's specified stack and structure; `uv` gives reproducible,
fast environment resolution consistent with the reproducibility principle.

**Alternatives considered**: Poetry/pip-tools — rejected; `uv` was specified.

---

## Resolved unknowns summary

| Topic | Resolution |
|-------|-----------|
| Money representation | `Decimal` at config precision; pandas for grouping only |
| Determinism mechanism | Canonical explicit ordering + stable mergesort everywhere |
| Current period source | Explicit engine input (not wall clock) |
| % denominator | `abs(comparator)`; zero → not_meaningful |
| Flag combination | value: abs AND %; margin: pp |
| Public contract | `FlaggedVariance` w/ `schema_version="1.0.0"` + JSON Schema snapshot |
| Repository signature | `get_transactions() -> list[Transaction]` |
| Config format isolation | `read_table` indirection; Pydantic validation at load |
| Excel parity | Write from `PnLResult` only; round-trip parity test |
| Traceability | Provenance index keyed by (line, scenario, time_cut) |
| Unmapped accounts | Build + warn; `ReconciliationStatus.residual` |
