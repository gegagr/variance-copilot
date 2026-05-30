# Phase 1 Data Model: Deterministic P&L and Variance Engine

All models are Pydantic v2. Money and ratios are `decimal.Decimal`. Enums fix the
canonical ordering used for deterministic output. Input (config + transaction) models live
in `config/schemas.py` and `engine/models.py`; output models live in `engine/models.py`.

## Enumerations (canonical order)

```python
class Scenario(str, Enum):        # comparison + display order
    PRIOR_YEAR    = "prior_year"
    CURRENT_YEAR  = "current_year"
    BUDGET        = "budget"

class TimeCut(str, Enum):         # column order
    PRIOR_MONTH_YTD = "prior_month_ytd"
    CURRENT_MONTH   = "current_month"
    YTD             = "ytd"
    FULL_YEAR       = "full_year"

class LineType(str, Enum):
    REVENUE  = "revenue"          # positive delta = favorable
    COST     = "cost"             # positive delta = unfavorable
    SUBTOTAL = "subtotal"
    MARGIN   = "margin"

class ValueKind(str, Enum):
    ACTUAL       = "actual"
    BUDGET       = "budget"
    LANDING      = "landing"       # current-year full-year only
    NOT_MEANINGFUL = "not_meaningful"  # zero-base margin marker

class ScenarioPair(str, Enum):
    CURRENT_VS_PRIOR_YEAR = "current_vs_prior_year"
    CURRENT_VS_BUDGET     = "current_vs_budget"
```

---

## Input models

### Transaction *(engine/models.py — the engine's input contract)*

| Field | Type | Rules |
|-------|------|-------|
| `transaction_id` | `str` | Non-empty, unique within a dataset. Used for provenance + canonical tie-break. |
| `gl_account` | `str` | Non-empty. Mapped via COA config. |
| `amount` | `Decimal` | EUR, quantized to money precision. Sign per declared convention. |
| `period` | `int` | 1..12 (fiscal month). |
| `scenario` | `Scenario` | prior_year \| current_year \| budget. |
| `entity` | `str` | FK into entities/geographies config. |
| `business_unit` | `str` | FK into business-structure config. |
| `project` | `str \| None` | Optional tag. |

**Canonical sort key**: `(scenario, entity, business_unit, gl_account, period, transaction_id)`.

### Config models *(config/schemas.py)*

**CoaMappingRow** — `gl_account: str`, `reporting_line: str`. Validation: each
`gl_account` maps to exactly one `reporting_line` (duplicate → config error, FR-024).

**BusinessUnitRow** — `business_unit: str`, `parent: str | None`. Validation: acyclic
hierarchy; every `parent` exists.

**EntityGeographyRow** — `entity: str`, `geography: str`, `rollup: str`. (v1: single
reporting currency EUR applies to all entities.)

**PnLLayoutRow** —
| Field | Type | Rules |
|-------|------|-------|
| `reporting_line` | `str` | Unique. |
| `order` | `int` | Unique; defines display + canonical line order. |
| `line_type` | `LineType` | revenue \| cost \| subtotal \| margin. |
| `components` | `list[str]` | Subtotals only: child reporting lines summed. Must exist; no cycles. |
| `margin_numerator` | `str \| None` | Margin lines only: line whose value is the numerator. |
| `margin_base` | `str \| None` | Margin lines only: line used as the denominator/base. |

Validation: subtotal `components` reference existing lines and form a DAG; margin
`numerator`/`base` reference existing lines; `order` values unique.

**ThresholdRow** — `rule_id: str`, `applies_to: Literal["value", "margin"]`,
`abs_threshold: Decimal`, `pct_threshold: Decimal`, `pp_threshold: Decimal`. The `value`
category covers revenue, cost, AND subtotal lines (flagged on abs AND %); `margin` covers
margin lines (flagged on pp). A line's category is derived from its `LineType`.

**ReportingSettings** — `reporting_currency: Literal["EUR"]`, `money_precision: int = 2`,
`ratio_precision: int = 6`, `current_period: int` (1..12), `not_meaningful_label: str =
"n/m"`, `sign_convention: Literal["natural_signed"] = "natural_signed"`.
Under `natural_signed`, amounts carry their natural sign (revenue positive, cost/expense
negative), so every subtotal is a plain sum of its component cells (FR-004). Favorable vs
unfavorable is still derived from `line_type`, never from the raw sign.

**EngineConfig** *(bundle)* — `coa`, `business`, `entities`, `layout`, `thresholds`,
`settings`. Built and fully validated by the shell loader; passed as one object to the core.

---

## Output models

### PnLCell

| Field | Type | Notes |
|-------|------|-------|
| `reporting_line` | `str` | |
| `scenario` | `Scenario` | |
| `time_cut` | `TimeCut` | |
| `value` | `Decimal` | The figure. |
| `value_kind` | `ValueKind` | actual \| budget \| landing \| not_meaningful. |
| `is_margin` | `bool` | True for margin-line cells (value is a ratio). |

### PnLLine

| Field | Type | Notes |
|-------|------|-------|
| `reporting_line` | `str` | |
| `order` | `int` | Canonical position. |
| `line_type` | `LineType` | |
| `cells` | `list[PnLCell]` | One per (scenario × time_cut), in enum order. |

### ReconciliationStatus

| Field | Type | Notes |
|-------|------|-------|
| `is_complete` | `bool` | False when unmapped accounts exist. |
| `residual` | `Decimal` | Σ unmapped amounts (0 when complete). |
| `unmapped_accounts` | `dict[str, Decimal]` | gl_account → total unmapped amount. |

### ProvenanceIndex

| Field | Type | Notes |
|-------|------|-------|
| `by_cell` | `dict[tuple[str, Scenario, TimeCut], frozenset[str]]` | leaf cell → contributing `transaction_id`s. Subtotals/margins trace transitively via layout. |

### PnLResult *(top-level core output #1)*

| Field | Type | Notes |
|-------|------|-------|
| `lines` | `list[PnLLine]` | In canonical `order`. |
| `reconciliation` | `ReconciliationStatus` | |
| `provenance` | `ProvenanceIndex` | |
| `reporting_currency` | `Literal["EUR"]` | Label only. |
| `current_period` | `int` | Echoed for traceability. |

### Variance

| Field | Type | Notes |
|-------|------|-------|
| `reporting_line` | `str` | |
| `line_type` | `LineType` | |
| `time_cut` | `TimeCut` | |
| `scenario_pair` | `ScenarioPair` | |
| `current_value` | `Decimal` | |
| `comparator_value` | `Decimal` | |
| `abs_variance` | `Decimal \| None` | `current - comparator`; None for margin lines. |
| `pct_variance` | `Decimal \| None` | `(current-comparator)/abs(comparator)`; None if not applicable. |
| `pp_variance` | `Decimal \| None` | margin lines only: `margin_current - margin_comparator`. |
| `is_meaningful` | `bool` | False when comparator is 0 for a pct variance. |
| `direction` | `Literal["favorable","unfavorable","neutral"]` | Under `natural_signed`, favorable = positive signed delta for every line type (the cost sign is carried by the amount): more revenue and less-negative cost both read favorable. |

### FlaggedVariance *(top-level core output #2 — VERSIONED PUBLIC CONTRACT)*

| Field | Type | Notes |
|-------|------|-------|
| `schema_version` | `Literal["1.0.0"]` | Bumped only by deliberate contract change. |
| `flag_id` | `str` | Deterministic id (hash of identifying fields). |
| `reporting_line` | `str` | |
| `line_type` | `LineType` | |
| `time_cut` | `TimeCut` | |
| `scenario_pair` | `ScenarioPair` | |
| `current_value` | `Decimal` | |
| `comparator_value` | `Decimal` | |
| `abs_variance` | `Decimal \| None` | |
| `pct_variance` | `Decimal \| None` | |
| `pp_variance` | `Decimal \| None` | |
| `direction` | `Literal["favorable","unfavorable"]` | |
| `rule_id` | `str` | The triggering rule from `thresholds.csv`. |
| `abs_threshold` | `Decimal` | Rule values captured for audit. |
| `pct_threshold` | `Decimal` | |
| `pp_threshold` | `Decimal` | |

`FlaggedVariance` is serialized to `contracts/flagged_variance.schema.json`; see
[contracts/flagged_variance.md](./contracts/flagged_variance.md).

---

## Core function signatures (pure — `engine/`)

```python
def build_pnl(transactions: list[Transaction], config: EngineConfig) -> PnLResult: ...

def compute_variances(result: PnLResult, config: EngineConfig) -> list[Variance]: ...

def flag_variances(variances: list[Variance], config: EngineConfig) -> list[FlaggedVariance]: ...
```

All three are deterministic, side-effect-free, and return outputs in canonical order.

## Validation & invariants (enforced by tests)

- **Reconciliation**: for fully-mapped data, every subtotal cell == Σ its component cells;
  every margin cell == numerator/base (quantized); `residual == 0`.
- **Determinism**: `build_pnl`/`compute_variances`/`flag_variances` produce byte-identical
  serialized output across repeated runs and across input permutations (after canonical
  sort).
- **Landing**: current-year full-year cell `value_kind == LANDING` and equals
  Σ(current-year actual, periods 1..p) + Σ(budget, periods p+1..12); never equals the YTD
  actual cell unless p == 12.
- **Traceability**: every leaf cell has a non-empty provenance set for non-empty periods.
- **Flag completeness**: every `FlaggedVariance` has all rule + value fields populated and
  validates against the pinned schema.
