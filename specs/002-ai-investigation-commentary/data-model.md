# Phase 1 Data Model: AI Investigation and Commentary Layer (Block 3)

All models are Pydantic v2 in `agent/models.py` (output contracts) and `config/agent_settings.py`
(config). Money/ratio values are `Decimal`. The three output contracts carry an explicit
`schema_version` and embed immutable evidence snapshots, mirroring Block 1's `FlaggedVariance`.

## Enumerations

```python
class RecordStatus(str, Enum):
    QUESTION = "question"
    DRAFT = "draft"

class AggregateOp(str, Enum):
    SUM = "sum"
    COUNT = "count"
    MIN = "min"
    MAX = "max"

class FigureSource(str, Enum):
    BLOCK1 = "block1"     # a Block 1 figure for the flag
    GL = "gl"             # an amount from a GL evidence row
    AGGREGATE = "aggregate"  # a code-computed aggregate over cited rows
```

## Input (from Block 1 / repository)

- **FlaggedVariance** *(reused from Block 1 `engine.models`)* — the flag under investigation.
- **PnLResult** *(reused)* — surrounding P&L context (FR-006); provides the verbatim Block 1
  figures admissible for the flag.

## GL evidence

### GLEvidenceRow *(embedded snapshot)*

| Field | Type | Notes |
|-------|------|-------|
| `transaction_id` | `str` | Stable id; used in references and aggregates. |
| `gl_account` | `str` | |
| `amount` | `Decimal` | Admissible verbatim figure. |
| `period` | `int` | 1..12 |
| `scenario` | `str` | |
| `date` | `str` (ISO) | Enriched fixture field. |
| `project` | `str \| None` | |
| `counterparty` | `str \| None` | Enriched fixture field. |
| `labels` | `list[str]` | Enriched fixture field. |

### GLQuery / GLQueryResult

- **GLQuery** — `reporting_line: str`, `period: int`, `scenario: str`, `filters: dict | None`.
- **GLQueryResult** — `query: GLQuery`, `rows: list[GLEvidenceRow]`. Read-only result of
  `query_gl_detail`; the rows form part of the flag's admissible value set.

## Figure references & aggregates (reference-and-render)

### AggregateSpec

| Field | Type | Notes |
|-------|------|-------|
| `agg_id` | `str` | Token id referenced as `{{fig:agg:<agg_id>}}`. |
| `op` | `AggregateOp` | sum / count / min / max. |
| `row_ids` | `list[str]` | Cited evidence `transaction_id`s the op runs over. |

### RenderedFigure *(audit of every number placed in text)*

| Field | Type | Notes |
|-------|------|-------|
| `token` | `str` | e.g. `{{fig:flag.current_value}}`, `{{fig:gl:T123.amount}}`, `{{fig:agg:a1}}`. |
| `source` | `FigureSource` | block1 / gl / aggregate. |
| `value` | `Decimal` | The value code rendered (never typed by the model). |
| `origin` | `str` | The Block 1 field name, the `transaction_id`, or the `agg_id`. |

## Output contracts (versioned)

### Hypothesis

| Field | Type | Notes |
|-------|------|-------|
| `text` | `str \| None` | Null when no hypothesis could be formed (sparse evidence). |
| `evidence_row_ids` | `list[str]` | The cited rows the hypothesis names. |

### Question *(versioned contract)*

| Field | Type | Notes |
|-------|------|-------|
| `schema_version` | `Literal["1.0.0"]` | |
| `question_id` | `str` | Deterministic from the flag id. |
| `flag_id` | `str` | Links to the Block 1 flag. |
| `text` | `str` | Fully rendered (figures substituted by code). |
| `hypothesis` | `Hypothesis` | Stated hypothesis (or null text for open question). |
| `evidence` | `list[GLEvidenceRow]` | Immutable snapshot of supporting rows. |
| `rendered_figures` | `list[RenderedFigure]` | Every number in `text`, with its source. |
| `llm_log_refs` | `list[str]` | Audit-log entry ids that produced it. |

### Draft *(versioned contract)*

| Field | Type | Notes |
|-------|------|-------|
| `schema_version` | `Literal["1.0.0"]` | |
| `draft_id` | `str` | Deterministic from the flag id. |
| `flag_id` | `str` | |
| `commentary` | `str` | Fully rendered management-commentary line. |
| `evidence` | `list[GLEvidenceRow]` | Immutable snapshot. |
| `rendered_figures` | `list[RenderedFigure]` | Every number, with source. |
| `controller_input` | `ControllerInput \| None` | Verbatim controller response (null if self-explanatory). |
| `provenance` | `DraftProvenance` | variance id + evidence row ids + controller input id. |
| `llm_log_refs` | `list[str]` | |
| `is_proposal` | `Literal[True]` | Always true — never finalized here (Principle IV). |

### InvestigationRecord *(versioned contract — top-level output, one per flag)*

| Field | Type | Notes |
|-------|------|-------|
| `schema_version` | `Literal["1.0.0"]` | |
| `flag_id` | `str` | |
| `variance` | `FlaggedVariance` | The linked Block 1 flag (embedded). |
| `status` | `RecordStatus` | question / draft. |
| `evidence` | `list[GLEvidenceRow]` | Immutable snapshot of all rows used. |
| `hypothesis` | `Hypothesis` | May have null text. |
| `question` | `Question \| None` | Present iff status == question. |
| `draft` | `Draft \| None` | Present iff status == draft (or after a response). |
| `llm_log_refs` | `list[str]` | All audit entries for this investigation. |

## Supporting types

- **ControllerInput** — `input_id: str`, `flag_id: str`, `text: str` (verbatim), `accepted_hypothesis: bool`.
- **DraftProvenance** — `flag_id: str`, `evidence_row_ids: list[str]`, `controller_input_id: str | None`.
- **LLMLogEntry** *(audit, `agent/audit.py`)* — `entry_id: str`, `ts: str`, `model: str`,
  `request: dict`, `response: dict`, `tool_calls: list[dict]`. API key never present.

## Config

### AgentSettings *(config/agent_settings.py)*

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `model_id` | `str` | — | OpenRouter model identifier (config, never hardcoded). |
| `temperature` | `Decimal` | `0` | Near-0 for repeatability. |
| `max_tool_calls_per_variance` | `int` | `4` | Bounds the investigation loop. |
| `dominant_share_threshold` | `Decimal` | `0.60` | If one row ≥ this share of |abs variance| → self-explanatory (Draft); else Question. |

## Core function signatures (ports injected)

```python
# agent/provider.py
class LLMProvider(Protocol):
    def complete(self, messages, tools, *, temperature, model) -> ProviderResponse: ...

# agent/tools.py
def query_gl_detail(repo: Repository, config: EngineConfig, query: GLQuery) -> GLQueryResult: ...

# agent/investigate.py  (provider-agnostic core)
def investigate(flag, pnl, *, provider, gl_tool, settings, audit, now) -> InvestigationRecord: ...

# agent/commentary.py
def render_draft(spec, evidence, allowed, *, controller_input) -> Draft: ...

# agent/guards.py  (pure, deterministic)
def assert_grounded(text: str, allowed: AllowedValues) -> GuardResult: ...
def assert_no_raw_digits(tokenized_text: str) -> GuardResult: ...
```

## Validation & invariants (enforced by tests)

- **No model-typed numbers**: structured model output contains figure tokens only; raw digits
  outside tokens fail `assert_no_raw_digits`.
- **Grounding**: every number in a rendered Question/Draft equals a verbatim source value or a
  recomputed aggregate; otherwise the output is rejected (`assert_grounded`).
- **One record per flag**: `len(records) == len(flags)`; status ∈ {question, draft}.
- **Provenance**: every Draft records variance id, evidence row ids, and controller input id.
- **Self-explanatory → no question**: when a dominant row clears the threshold, status is draft
  with no Question emitted.
- **Sparse evidence → open question, null hypothesis**: no invented driver.
- **Audit**: one log entry per LLM call with ts/model/request/response; API key absent; each
  output links to its entry id.
- **Contracts**: Question/Draft/InvestigationRecord validate against their JSON Schemas;
  `schema_version` pinned at `1.0.0`.
