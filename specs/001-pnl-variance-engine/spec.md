# Feature Specification: Deterministic P&L and Variance Engine

**Feature Branch**: `001-pnl-variance-engine`

**Created**: 2026-05-30

**Status**: Draft

**Input**: User description: "Specify the first feature: the deterministic P&L and variance engine. This is the computational core — every number in the application originates here. It builds a configurable management P&L from transaction-level data, computes variances across scenarios and time periods, and flags material variances for review. Per the constitution, no LLM is involved in this feature at all."

## Overview

This feature is the computational core of Variance Copilot: a deterministic engine
that turns transaction-level financial data into a configurable management P&L,
computes variances across scenarios and time periods, and flags the variances that
cross materiality rules. No language model participates in this feature — every
figure is produced by deterministic calculation, in keeping with the project
constitution (Determinism First, Auditability). The engine reads data through a
defined data-access interface and reads all structure from editable config files;
it does not implement any data-source connector, AI layer, web UI, or Word export.

## Clarifications

### Session 2026-05-30

- Q: What triggers a flag when a value line has thresholds in both absolute and percentage terms? → A: Value lines flag only when the absolute AND the percentage threshold are both breached (de-minimis guard); margin lines flag on the percentage-point threshold alone.
- Q: How are figures represented and rounded so reconciliation is exact and runs reproducible? → A: Exact fixed-point decimal arithmetic stored at full configured precision; subtotals are the exact sum of stored components (reconciliation holds to the cent); display rounding is a separate presentation concern.
- Q: How is a negative or unusual comparator handled in percentage variances? → A: % variance = (current − comparator) / |comparator| (signed numerator, absolute-value denominator); zero comparator → "not meaningful"; favorable/unfavorable comes from line type, not the raw sign.
- Q: What does the engine do when some GL accounts are not mapped to a reporting line? → A: Build the P&L from mapped transactions, emit the explicit unmapped-accounts report, and mark the run as "incomplete / does not fully reconcile" with residual = sum of unmapped amounts; exact reconciliation is guaranteed only for fully-mapped datasets.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Build the management P&L from transactions and config (Priority: P1)

A finance controller has transaction-level data and a set of config files that
describe how their P&L is structured. They run the engine and receive a fully
built management P&L for a chosen scenario and time cut: raw GL accounts mapped to
reporting lines, lines aggregated and ordered exactly as the layout config
dictates, subtotals (e.g. net contribution, EBITDA) computed, and margin %
lines shown beneath the subtotals they belong to. The total ties back to the
source transactions with no unexplained residual.

**Why this priority**: Without the structured P&L there is nothing to compare,
flag, or export. This is the foundational slice that delivers standalone value —
a controller can already replace a manual mapping-and-aggregation spreadsheet.

**Independent Test**: Provide a fixed transaction set and the four config files,
request one scenario/time-cut, and confirm the returned P&L matches an
independently hand-computed expected result line-for-line, with every subtotal
equal to the sum of its components and the grand total reconciling to the source.

**Acceptance Scenarios**:

1. **Given** transactions tagged with GL accounts and a chart-of-accounts mapping,
   **When** the engine builds the P&L, **Then** each transaction's amount lands on
   the reporting line its GL account maps to, and any GL account not present in the
   mapping is surfaced in an explicit "unmapped accounts" report rather than
   silently dropped. The P&L is still built from the mapped transactions, but the
   run is marked "incomplete / does not fully reconcile" with residual equal to the
   sum of the unmapped amounts.
2. **Given** a P&L layout config defining line order, subtotal lines, and margin
   lines with their bases, **When** the engine builds the P&L, **Then** the output
   presents lines in the configured order, every subtotal equals the sum of its
   declared component lines, and each margin line equals its numerator line divided
   by its configured base.
3. **Given** a margin line whose base evaluates to zero for a period, **When** the
   engine computes that margin, **Then** the engine returns a defined zero-base
   result (not an error or crash) and marks the cell so the condition is
   distinguishable from a genuine 0%.

---

### User Story 2 - Produce scenarios across time cuts, including the labeled landing (Priority: P2)

The controller needs each reporting line populated for three scenarios — prior-year
actuals, current-year, and current-year budget — across four time cuts: prior-month
YTD, current month, YTD, and full year. For the current-year scenario, the full-year
column is a landing estimate (actuals for elapsed periods plus budget for the
remaining periods) and is labeled distinctly as a forecast/landing, never presented
as pure actuals.

**Why this priority**: The scenario-by-time-cut grid is the data substrate every
variance and flag is computed from. The landing-vs-actuals distinction is a core
correctness guarantee — conflating them would misstate the year.

**Independent Test**: For a fixed dataset where the current period is known, request
all scenarios and time cuts and confirm: true YTD actuals and the full-year landing
appear as separate, clearly named columns; the landing equals elapsed actuals plus
remaining budget; and the landing column carries an explicit forecast label in the
output.

**Acceptance Scenarios**:

1. **Given** a defined current period within the fiscal year, **When** the engine
   produces the current-year full-year column, **Then** it equals the sum of
   actuals for elapsed periods plus budget for the remaining periods, and the value
   is labeled as a landing/forecast.
2. **Given** the current-year scenario, **When** the engine produces YTD and the
   full-year landing, **Then** the two are returned as distinct, separately named
   columns that the output never merges or relabels as one another.
3. **Given** a time cut with no transactions for a scenario (e.g. an empty period),
   **When** the engine builds that column, **Then** it returns a defined zero/empty
   result without failure and the column is still present in the output.

---

### User Story 3 - Compute variances for every line (Priority: P3)

For every reporting line the controller needs two variance comparisons — current vs
prior year and current vs budget — each expressed in absolute and percentage terms.
For margin lines, the variance is expressed in percentage points.

**Why this priority**: Variances are the controller's actual review surface and the
input to materiality flagging. They depend on Story 2's scenario grid but add the
distinct value of quantifying movement.

**Independent Test**: For a fixed scenario grid, confirm each line's absolute
variance equals current minus comparator, each percentage variance equals absolute
variance over the comparator (with a defined rule when the comparator is zero), and
each margin line's variance is expressed as a percentage-point difference, not a
percentage-of-percentage.

**Acceptance Scenarios**:

1. **Given** a populated scenario grid, **When** the engine computes variances,
   **Then** every non-margin line carries current-vs-prior-year and current-vs-budget
   variances in both absolute and percentage form.
2. **Given** a margin line, **When** the engine computes its variance, **Then** the
   variance is a percentage-point difference between the two margin values, clearly
   distinguished from an absolute or percentage variance.
3. **Given** a comparator value of zero, **When** the engine computes a percentage
   variance, **Then** it applies a defined, documented rule for the zero-comparator
   case rather than producing an undefined or error value.

---

### User Story 4 - Flag material variances against configurable rules (Priority: P4)

The controller needs the engine to flag the variances that matter, using
configurable thresholds expressed simultaneously in absolute-value, percentage, and
percentage-point terms. Each flag records exactly why it fired so it can be audited
and consumed downstream.

**Why this priority**: Flagging turns a wall of numbers into a review queue and
produces the flag schema that the later AI commentary feature depends on as a public
contract. It builds on Story 3's variances.

**Independent Test**: With thresholds set to known values, confirm that a variance
crossing its rule is flagged and one below it is not, and that each flag carries the
reporting line, time cut, scenario pair, underlying values, computed variance, and
the identity of the rule that triggered it.

**Acceptance Scenarios**:

1. **Given** configured thresholds, **When** a value line breaches BOTH its absolute
   AND its percentage threshold (or a margin line breaches its percentage-point
   threshold), **Then** a flag is produced; **When** a value line breaches only one of
   absolute or percentage (or neither), **Then** no flag is produced for it.
2. **Given** a produced flag, **When** it is inspected, **Then** it records the
   reporting line, time cut, scenario pair compared, the underlying scenario values,
   the computed variance, and the named/identified rule that triggered it.
3. **Given** the flag output as a whole, **When** it is consumed by a downstream
   reader, **Then** it conforms to a documented, versioned schema treated as a stable
   public interface.

---

### User Story 5 - Export the P&L to Excel (Priority: P5)

The controller exports the built P&L to an Excel file that preserves the line
hierarchy, subtotals, and margin lines so it can be opened and read outside the
tool.

**Why this priority**: Excel is a first-class output per the constitution and a
common controller workflow, but it depends on the P&L being built first and adds
distribution rather than computation value.

**Independent Test**: Export a known P&L and confirm the resulting workbook contains
the same lines in the same order, with subtotals and margin lines preserved and the
same figures as the in-memory P&L object.

**Acceptance Scenarios**:

1. **Given** a built P&L, **When** the controller exports to Excel, **Then** the
   workbook preserves reporting-line order, subtotal lines, and margin lines as
   structured in the P&L object.
2. **Given** a built P&L with multiple scenarios and time cuts, **When** exported,
   **Then** every figure in the workbook equals the corresponding figure in the P&L
   object (no rounding or value differences introduced by export).

---

### Edge Cases

- **Unmapped GL accounts**: surfaced in an explicit report; never silently dropped
  or absorbed into a catch-all line without notice.
- **Zero-base margins**: a margin whose base is zero returns a defined result and is
  marked, distinguishable from a true 0%.
- **Zero comparator in percentage variance**: result marked "not meaningful" rather
  than a division-by-zero failure.
- **Negative comparator in percentage variance**: denominator uses the absolute value
  of the comparator so the percentage magnitude stays intuitive for negative bases
  (e.g. a prior-year loss); direction comes from line type, not the raw sign.
- **Empty periods**: a time cut with no transactions yields a defined zero/empty
  column without failure.
- **Current period at fiscal-year boundaries**: when the current period is the first
  period (no elapsed actuals) or the last period (no remaining budget), the landing
  estimate still computes correctly from whatever portion exists.
- **Reporting currency**: v1 assumes all entities report in a single common currency
  (declared in config); multi-currency consolidation is deferred to a later spec.
- **Duplicate or conflicting config entries** (e.g. one GL account mapped to two
  reporting lines): surfaced as an explicit configuration error rather than producing
  a silently wrong total.
- **Subtotal that does not reconcile**: any residual between a subtotal and the sum
  of its components is surfaced rather than hidden.

## Requirements *(mandatory)*

### Functional Requirements

**Mapping & aggregation**

- **FR-001**: The engine MUST map each transaction's GL account to a reporting line
  according to the chart-of-accounts config.
- **FR-002**: The engine MUST surface every GL account that has no mapping in an
  explicit unmapped-accounts report and MUST NOT silently drop or reassign it. The
  engine MUST still build the P&L from the mapped transactions and MUST mark the run
  as "incomplete / does not fully reconcile", recording a residual equal to the sum
  of the unmapped amounts. (Exact reconciliation per FR-027 is guaranteed only for
  fully-mapped datasets.)
- **FR-003**: The engine MUST aggregate mapped amounts into reporting lines and
  present them in the exact order defined by the P&L layout config.
- **FR-004**: The engine MUST compute every subtotal line (e.g. net contribution,
  EBITDA) as the sum of its declared component lines as defined in the layout config.
- **FR-005**: The engine MUST compute every margin % line as its configured numerator
  line divided by its configured base line, positioned beneath the subtotal it
  belongs to per the layout config.

**Scenarios & time cuts**

- **FR-006**: The engine MUST produce values for three scenarios — prior-year
  actuals, current-year, and current-year budget.
- **FR-007**: The engine MUST produce each scenario across four time cuts —
  prior-month YTD, current month, YTD, and full year.
- **FR-008**: The engine MUST compute the current-year full-year column as a landing
  estimate equal to actuals for elapsed periods plus budget for remaining periods.
- **FR-009**: The engine MUST label the current-year full-year landing distinctly as
  a forecast/landing and MUST keep true YTD actuals and the full-year landing as
  separate, clearly named columns that are never conflated.

**Variances**

- **FR-010**: The engine MUST compute, for every line, a current-vs-prior-year and a
  current-vs-budget variance in both absolute and percentage terms. The percentage
  variance MUST be computed as (current − comparator) / |comparator| — a signed
  numerator over the absolute value of the comparator — so the magnitude is intuitive
  even when the comparator (base) is negative.
- **FR-011**: The engine MUST express variances for margin lines in percentage points
  rather than as a percentage of a percentage.
- **FR-012**: The engine MUST mark a percentage variance as "not meaningful" when the
  comparator value is zero, rather than dividing by zero or failing. Favorable vs
  unfavorable direction MUST be derived from the reporting line's type (FR-013), not
  from the raw sign of the percentage.
- **FR-013**: The engine MUST determine for each variance whether it is favorable or
  unfavorable based on the reporting line's type (revenue vs cost) as declared in
  config, so direction is derivable downstream.

**Data model & flagging**

- **FR-014**: The engine MUST express the full data model — scenario values across
  the four time cuts plus the variance columns — as one explicit, documented schema.
- **FR-015**: The engine MUST flag variances using configurable thresholds expressed
  in absolute-value, percentage, and percentage-point terms, combined as follows:
  a value (non-margin) line is flagged only when BOTH its absolute AND its percentage
  threshold are breached (de-minimis guard); a margin line is flagged when its
  percentage-point threshold is breached. The combination rule MUST be applied
  consistently and be derivable from config + line type.
- **FR-016**: Each flag MUST record the reporting line, time cut, scenario pair
  compared, the underlying scenario values, the computed variance, and the identity
  of the specific rule that triggered it.
- **FR-017**: The flag list MUST conform to a documented, versioned schema treated as
  a stable public interface for the later AI commentary feature.

**Currency**

- **FR-018**: The engine MUST operate in a single reporting currency for v1, declared
  in config; all transactions are assumed to be denominated in that currency.
  Multi-currency consolidation and FX conversion are deferred to a later spec and are
  out of scope here. The data model and config MUST not preclude adding entity-level
  currency and FX consolidation later without breaking the v1 contract.

**Outputs**

- **FR-019**: The engine MUST return the full P&L as a structured, documented data
  object.
- **FR-020**: The engine MUST return the list of flagged variances in the versioned
  schema of FR-017.
- **FR-021**: The engine MUST provide an Excel export of the P&L that preserves line
  hierarchy, subtotals, and margin lines, with figures identical to the P&L object.

**Configuration & data access**

- **FR-022**: The engine MUST read all structure — chart-of-accounts mapping, business
  structure (business-unit hierarchy), entities and geographies (entity → geography →
  rollup), and P&L layout — from editable config files, not from code; changing
  layout, mappings, rollups, or thresholds MUST require only config edits.
- **FR-023**: The engine MUST consume transaction data exclusively through the defined
  data-access interface and MUST NOT depend on any specific data source
  (no Supabase- or CSV-specific logic in the engine).
- **FR-024**: The engine MUST validate config on load and surface conflicting or
  duplicate entries (e.g. a GL account mapped to multiple reporting lines) as explicit
  configuration errors.

**Determinism, reconciliation, traceability**

- **FR-025**: The engine MUST be deterministic and reproducible: identical inputs plus
  identical config MUST always produce identical outputs.
- **FR-026**: No figure in any output may originate from a language model; every number
  MUST be produced by deterministic calculation.
- **FR-027**: The engine MUST reconcile: every subtotal equals the sum of its
  components, every margin equals its line divided by its defined base, and the P&L
  ties to source data with no unexplained residual.
- **FR-028**: The engine MUST enable traceability of every reported figure back to the
  source transactions that produced it.
- **FR-029**: The engine MUST perform all financial arithmetic in exact fixed-point
  decimal at the configured precision, storing values at full precision. Subtotals
  MUST equal the exact sum of their stored component values (reconciliation holds to
  the cent). Any rounding for display is a separate presentation concern and MUST NOT
  alter stored figures or break subtotal/margin reconciliation. Floating-point
  arithmetic MUST NOT be used for stored financial figures.

### Key Entities *(include if feature involves data)*

- **Transaction**: A single financial record — GL account, amount, date, and
  project / entity / business-unit tags. The atomic input the P&L is built from.
- **Chart-of-Accounts Mapping**: Config relating each GL account to a reporting line.
- **Business Structure**: Config defining the business-unit hierarchy.
- **Entity / Geography Rollup**: Config relating each entity to a geography and a
  rollup. (v1: a single common reporting currency applies to all entities.)
- **P&L Layout**: Config defining reporting-line order, which lines are subtotals and
  their components, and which margin % lines appear and against which base.
- **Reporting Line**: A line in the management P&L (regular, subtotal, or margin),
  typed as revenue or cost for favorable/unfavorable determination.
- **Scenario**: One of prior-year actuals, current-year, current-year budget.
- **Time Cut**: One of prior-month YTD, current month, YTD, full year (full year for
  current-year is the labeled landing).
- **P&L Value (Cell)**: A figure for a (reporting line × scenario × time cut), with a
  label distinguishing actuals from the landing/forecast and marking zero-base cases.
- **Variance**: A computed comparison for a (line × time cut × scenario pair) in
  absolute, percentage, and — for margins — percentage-point terms, plus a
  favorable/unfavorable indicator.
- **Threshold Rule**: A named/identified materiality rule expressed in absolute,
  percentage, and percentage-point terms.
- **Variance Flag**: A record that a variance crossed its rule, capturing line, time
  cut, scenario pair, underlying values, computed variance, and triggering rule;
  emitted in the versioned public schema.
- **Reconciliation Status**: A property of a build run indicating whether it fully
  reconciles or is "incomplete", including the residual amount (sum of unmapped GL
  amounts) and a reference to the unmapped-accounts report.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Running the engine twice on identical inputs and config produces
  byte-for-byte identical P&L objects and flag lists (100% reproducibility).
- **SC-002**: 100% of subtotals equal the sum of their declared components, and 100%
  of margin lines equal numerator ÷ base, across all scenarios and time cuts in the
  validation dataset.
- **SC-003**: The built P&L ties to source transactions with zero unexplained residual
  for every fully mapped dataset.
- **SC-004**: 100% of GL accounts absent from the chart-of-accounts mapping appear in
  the unmapped-accounts report; none are silently dropped.
- **SC-005**: Every reported figure can be traced to the set of source transactions
  behind it for 100% of P&L cells in the validation dataset.
- **SC-006**: A controller can change P&L layout, account mappings, rollups, or
  materiality thresholds and see the change reflected in outputs by editing config
  files only, with zero code changes.
- **SC-007**: The current-year full-year landing equals elapsed actuals plus remaining
  budget for every tested current-period position, and is never presented as pure
  actuals (verified by the forecast label being present on 100% of landing columns).
- **SC-008**: Every produced flag includes all required fields (line, time cut,
  scenario pair, underlying values, computed variance, triggering rule) — 100% field
  completeness — and validates against the published flag schema version.
- **SC-009**: The engine handles empty periods, zero-base margins, and zero-comparator
  variances on the validation dataset without any unhandled failure.
- **SC-010**: The Excel export reproduces 100% of P&L figures with no value
  differences from the in-memory P&L object, preserving line order, subtotals, and
  margins.

## Assumptions

- **Single fiscal calendar**: All scenarios and time cuts share one fiscal-year
  calendar; period boundaries (months) are consistent across entities. The "current
  period" is supplied as an input so the YTD/landing split is unambiguous and
  deterministic.
- **Scenario coverage**: Prior-year actuals, current-year actuals (for elapsed
  periods), and budget data are all available through the data-access interface for
  the periods required by the four time cuts.
- **Sign convention**: Amounts use the `natural_signed` convention declared in config
  (`ReportingSettings.sign_convention`): revenue positive, cost/expense negative, so each
  subtotal is a plain sum of its components. Favorable/unfavorable is derived from
  reporting-line type, not from sign alone.
- **Zero-comparator rule**: Percentage variances against a zero comparator are marked
  "not meaningful" rather than computed; negative comparators use an absolute-value
  denominator (FR-010). The exact "not meaningful" label is fixed during planning.
- **Numeric precision**: All arithmetic is exact fixed-point decimal at a
  config-declared precision (FR-029); no floating-point for stored figures. Reconciliation
  is therefore exact, not tolerance-based.
- **Single reporting currency (v1)**: All entities report in one common currency,
  declared in config, and all transactions are denominated in it. Multi-currency
  consolidation and FX conversion (rate source, period-average vs closing basis, etc.)
  are deferred to a later spec; the v1 data model is designed not to preclude adding
  them later.
- **Data-access interface is provided**: This feature consumes transactions through a
  defined repository/data-access interface; the Supabase and CSV implementations of
  that interface are out of scope and specified separately.
- **Determinism of inputs**: The data-access interface returns transactions in a
  deterministic, stable manner (or the engine sorts to a canonical order) so that
  identical inputs yield identical outputs.
- **Mock data only**: Per the constitution, all data used for development and testing
  is mock data; no real client data is committed to the repository.

## Out of Scope

- Data-source connectors (Supabase, CSV import, or any other backing store).
- The AI investigation/commentary layer and the `query_gl_detail` tool.
- The web UI.
- Word export.
- Multi-currency consolidation and FX conversion (v1 is single reporting currency).
- Authentication, user management, and multi-tenant access control.
