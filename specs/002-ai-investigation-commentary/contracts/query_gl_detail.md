# Contract: query_gl_detail tool (read-only GL access)

The agent's only window into transaction detail (Constitution Principle III). Defined both as a
JSON tool the model can call and as a Python function bound to the Block 1/2 `Repository`
(`FixtureRepository` in this block). Read-only — no mutation path exists.

## Tool schema (exposed to the model)

```json
{
  "name": "query_gl_detail",
  "description": "Return the GL transaction rows behind a reporting line / period / scenario.",
  "parameters": {
    "type": "object",
    "additionalProperties": false,
    "required": ["reporting_line", "period", "scenario"],
    "properties": {
      "reporting_line": { "type": "string" },
      "period": { "type": "integer", "minimum": 1, "maximum": 12 },
      "scenario": { "type": "string", "enum": ["prior_year", "current_year", "budget"] },
      "filters": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "project": { "type": "string" },
          "counterparty": { "type": "string" },
          "label": { "type": "string" }
        }
      }
    }
  }
}
```

## Python binding

```python
# agent/tools.py
def query_gl_detail(repo: Repository, config: EngineConfig, query: GLQuery) -> GLQueryResult:
    """Resolve reporting_line -> GL accounts via the Block 1 COA config, select the matching
    scenario/period transactions (applying optional filters), and return GLEvidenceRow snapshots.
    Read-only. No write path."""
```

### Behavior & guarantees

- `reporting_line` resolves to its GL accounts using the Block 1 chart-of-accounts config; a
  subtotal/margin line resolves to the union of its component leaf accounts.
- Returns `GLEvidenceRow`s with `transaction_id, gl_account, amount (Decimal), period, scenario,
  date, project, counterparty, labels`.
- The returned `amount`s become part of the flag's admissible value set for the traceability
  guard.
- Read-only and source-agnostic: bound to the `Repository` abstraction, `FixtureRepository` here;
  Block 2 backends satisfy the same call with no agent change.

## Contract tests

- Querying a known (line, period, scenario) returns exactly the matching fixture rows.
- A subtotal line returns the union of its components' rows.
- Filters narrow results correctly (project / counterparty / label).
- No method on the tool mutates the repository.
