# Contract: FlaggedVariance (public, versioned)

`FlaggedVariance` is the **public interface** that Block 3 (the AI commentary layer)
consumes. It is the only output of Block 1 that another block depends on by shape, so it is
versioned and change-controlled.

- **Current version**: `1.0.0` (pinned as a `Literal` on the model and a `const` in the
  JSON Schema).
- **Schema file**: [flagged_variance.schema.json](./flagged_variance.schema.json).
- **Source of truth**: the Pydantic `FlaggedVariance` model in `engine/models.py`.

## Versioning policy

- Adding an **optional** field that downstream can ignore → MINOR bump (`1.1.0`).
- Removing/renaming a field, changing a type, or changing semantics → MAJOR bump (`2.0.0`).
- The `schema_version` literal and the JSON Schema `const` MUST be updated together.
- A contract test exports the live model's JSON Schema and asserts it equals the committed
  `flagged_variance.schema.json`. Drift fails the build — the contract cannot change
  silently.

## Serialization rules

- All `Decimal` fields serialize as **strings** to preserve exact precision across the
  block boundary (no float coercion).
- `abs_variance` / `pp_variance` are mutually exclusive by line type: value lines populate
  `abs_variance` (and `pct_variance`); margin lines populate `pp_variance`.
- `flag_id` is deterministic — derived from `(reporting_line, time_cut, scenario_pair,
  rule_id)` — so the same flag has the same id across runs (supports dedupe in Block 3).

## Example

```json
{
  "schema_version": "1.0.0",
  "flag_id": "ebitda|ytd|current_vs_budget|ebitda_value_rule",
  "reporting_line": "ebitda",
  "line_type": "subtotal",
  "time_cut": "ytd",
  "scenario_pair": "current_vs_budget",
  "current_value": "1250000.00",
  "comparator_value": "1500000.00",
  "abs_variance": "-250000.00",
  "pct_variance": "-0.166667",
  "pp_variance": null,
  "direction": "unfavorable",
  "rule_id": "value_default",
  "abs_threshold": "100000.00",
  "pct_threshold": "0.050000",
  "pp_threshold": "0.000000"
}
```
