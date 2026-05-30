# Quickstart: AI Investigation and Commentary Layer (Block 3)

Block 3 adds the `agent/` package to the existing project. The agent core is offline and
provider-agnostic; only the OpenRouter adapter makes network calls, and only at real runtime.

## Prerequisites

- Block 1 working (`uv sync` already done).
- For a *live* run only: an OpenRouter API key.

```bash
export OPENROUTER_API_KEY=sk-...        # live runs only; never commit, never logged
```

The test suite needs **no** key and makes **no** network calls.

## Run the investigation pipeline (live)

```bash
uv run python -m shell.investigate_pipeline \
    --config-dir config --sample-dir sample --current-period 6 \
    --out build/investigations.jsonl
```

This wires the imperative shell:

1. Block 1: `build_pnl` → `compute_variances` → `flag_variances` produces the flags + context.
2. `OpenRouterProvider` (the only network site) is constructed from `AgentSettings`.
3. For each flag, `investigate(...)` runs the loop: the model calls `query_gl_detail` (bound to
   `FixtureRepository`) to gather evidence, then emits a structured Question or Draft.
4. The traceability guard renders + validates every figure; the audit log is appended per call.
5. One `InvestigationRecord` per flag is written to `build/investigations.jsonl`.

## Use the agent core directly (offline, fake provider)

```python
from agent.fakes import FakeLLMProvider, tool_call, final
from agent.investigate import investigate

provider = FakeLLMProvider([
    tool_call("query_gl_detail", {"reporting_line": "ebitda", "period": 6, "scenario": "current_year"}),
    final({"status": "draft", "narrative": "EBITDA outperformed budget, driven by {{fig:gl:T...amount}} ...",
           "evidence_row_ids": ["T..."], "aggregates": []}),
])
record = investigate(flag, pnl, provider=provider, gl_tool=gl_tool,
                     settings=settings, audit=audit, now="2026-05-30T00:00:00Z")
assert record.status in ("question", "draft")
```

No key, no network — fully deterministic.

## Run the tests

```bash
uv run pytest tests/test_guards.py            # the traceability guard (most-tested)
uv run pytest tests/test_investigate_loop.py  # end-to-end loop with the fake provider
uv run pytest                                  # everything, offline
```

## The traceability guard (the constitutional core)

Every number that reaches a Question or Draft is **rendered by code**, never typed by the model:

- The model emits placeholders — `{{fig:flag.current_value}}`, `{{fig:gl:T123.amount}}`,
  `{{fig:agg:a1}}` — and the cited evidence / aggregate specs.
- `agent/commentary.py` substitutes the actual `Decimal` values from the allowed set
  (Block 1 figures + GL amounts + code-computed aggregates over cited rows).
- `agent/guards.py::assert_grounded` re-extracts every number from the rendered text and rejects
  any value that is neither a verbatim source value nor an independently recomputed aggregate.

If the guard fails, the output is not shown — it is logged and eligible for one bounded retry.

## Config & safety

- Agent settings live in `config/agent_settings.csv` (model id, temperature, max tool calls,
  question policy) — no model name in code (Principle V).
- All GL data is **mock** (Principle VIII). The API key is env-only and is never written to the
  audit log.
