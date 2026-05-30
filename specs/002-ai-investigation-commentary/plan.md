# Implementation Plan: AI Investigation and Commentary Layer (Block 3)

**Branch**: `002-ai-investigation-commentary` | **Date**: 2026-05-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-ai-investigation-commentary/spec.md`

## Summary

Block 3 turns Block 1's deterministic `FlaggedVariance` records into explained management
commentary. For each flag, an AI agent investigates the GL detail behind it (via a read-only
`query_gl_detail` tool bound to the fixture repository), forms a hypothesis, and emits one
structured `InvestigationRecord` that is either a grounded **Question** or a **Draft**. When a
controller response is supplied, the agent drafts concise commentary.

Technical approach: **ports-and-adapters (hexagonal)**. The agent core depends only on two
injected ports — `LLMProvider` (a tool-calling gateway, one OpenRouter adapter) and
`query_gl_detail` (read-only GL access) — so the whole loop is testable offline with a fake
provider. The constitution's hard line is enforced in deterministic Python: **the model emits
no digits** (it references figures/evidence by id and emits placeholders), **code renders every
number** (verbatim source values or code-computed aggregates over cited rows), and a **pure
traceability guard** rejects any output containing a number that is neither. Every LLM
interaction is appended to a JSON-lines audit log (prompt, response, model id, timestamp; never
the API key). All output is a proposal — accept/edit/dismiss is out of scope.

## Technical Context

**Language/Version**: Python 3.12+, managed with `uv` (same project as Block 1).

**Primary Dependencies**: Pydantic v2 (output models + structured-output validation),
`httpx` (OpenRouter HTTP calls, in the adapter only), pytest. Block 1 packages (`engine/`,
`config/`, `data/`) are reused. Standard-library `decimal`, `json`, `re`, `datetime`.

**Storage**: Committed mock GL fixtures (Block 1 `sample/`, enriched with date / counterparty /
labels). Audit log written as JSON lines to a run-scoped path. No database; no real connectors.

**Testing**: pytest. ALL LLM calls mocked via a fake `LLMProvider` — no network in the suite.
The traceability guard is the most heavily tested unit, including adversarial cases.

**Target Platform**: Local/CLI library (offline except the OpenRouter adapter at real runtime).

**Project Type**: Single Python project; adds an `agent/` package (ports + adapters + core).

**Performance Goals**: Not latency-bound. Bounded tool calls per variance (config). Correctness
and groundedness dominate.

**Constraints**: The model MUST NOT emit numeric digits; every rendered number is created by
deterministic Python (Determinism First). API key via env var only — never committed, never
logged. Agent core contains zero SDK/HTTP calls. Temperature near-0 for repeatability. All
output is a proposal; nothing is finalized here.

**Scale/Scope**: One InvestigationRecord per flag; single question round per flag; fixture data
only. Three versioned output contracts (InvestigationRecord, Question, Draft).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | How this plan complies | Status |
|---|-----------|------------------------|--------|
| I | Determinism First | The model emits **no digits**; it references figures/evidence by id and code renders every number — verbatim source values or code-computed aggregates verified by Python. The traceability guard rejects any stray number. No figure originates from the LLM. | ✅ PASS |
| II | Auditability | Every LLM interaction is appended to a JSON-lines audit log (prompt, response, model id, timestamp). Each Question/Draft links to its log entry. Each record embeds an immutable GL-evidence snapshot. | ✅ PASS |
| III | LLM Scope (investigate-and-draft only) | The agent only reads GL via the read-only `query_gl_detail` tool, forms hypotheses, asks, or drafts. No write access, no number production. Asks-not-asserts; open question on sparse evidence. | ✅ PASS |
| IV | Human in the Loop | All output is a proposal. Accept/edit/dismiss, finalization, and report assembly are explicitly out of scope; drafting is gated on a controller response for Question-status records. | ✅ PASS |
| V | Config-Driven, Not Hardcoded | Model id, temperature, max tool calls, and the self-explanatory-vs-question policy are config. No model name hardcoded in core. | ✅ PASS |
| VI | Source-Agnostic Data | GL access is the `query_gl_detail` port bound to the Block 1 `Repository`; `FixtureRepository` in this block. The agent core never touches a data source directly. | ✅ PASS |
| VII | Excel & Word Export First-Class | N/A to this block (report assembly/export is out of scope). No conflict introduced. | ✅ N/A |
| VIII | No Real Client Data | Mock GL fixtures only; `.gitignore` (Block 1) protects real inputs. API key via env var, never committed, never logged. | ✅ PASS |

**Result**: PASS. No violations — Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/002-ai-investigation-commentary/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── investigation_record.schema.json
│   ├── question.schema.json
│   ├── draft.schema.json
│   ├── llm_provider.md          # the LLMProvider port contract
│   └── query_gl_detail.md       # the GL tool contract
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root — additions to the Block 1 project)

```text
agent/                           # Block 3: ports-and-adapters AI layer
├── __init__.py
├── models.py                    # InvestigationRecord, Question, Draft, GLEvidenceRow,
│                                #   Hypothesis, RenderedFigure, LLMLogRef (versioned contracts)
├── provider.py                  # LLMProvider PORT (Protocol/ABC) + OpenRouterProvider ADAPTER
├── tools.py                     # query_gl_detail tool: schema + impl bound to the repository
├── investigate.py               # the investigation loop (provider-agnostic core)
├── commentary.py                # drafting: reference→render figure substitution
├── guards.py                    # the deterministic traceability validator (heavily tested)
├── audit.py                     # JSON-lines LLM interaction log (key never written)
└── fakes.py                     # FakeLLMProvider for offline deterministic tests

config/                          # additions
├── agent_settings.py            # AgentSettings schema (model id, temperature, max_tool_calls, policy)
└── agent_settings.csv           # mock agent config values

sample/                          # enriched GL fixtures (mock only)
└── gl_detail.csv                # transaction-level rows incl. date, counterparty, labels

shell/                           # additions
└── investigate_pipeline.py      # imperative composition root for Block 3

tests/
├── test_guards.py               # traceability guard — adversarial + happy path (MOST tested)
├── test_investigate_loop.py     # end-to-end loop with FakeLLMProvider + query_gl_detail
├── test_commentary.py           # reference→render substitution; no model-typed numbers
├── test_query_gl_detail.py      # tool returns correct rows; read-only
├── test_audit.py                # log has prompt/response/model/timestamp; no API key
├── test_contract_investigation.py  # InvestigationRecord schema + drift guard
├── test_contract_question.py    # Question schema + grounding
└── test_contract_draft.py       # Draft schema + provenance
```

**Structure Decision**: Ports-and-adapters layered on the existing Block 1 project. The
**agent core** (`investigate.py`, `commentary.py`, `guards.py`, `models.py`) contains zero SDK
or HTTP calls and depends only on the two injected ports — `LLMProvider` (`provider.py`) and the
`query_gl_detail` tool (`tools.py`, bound to the Block 1 `Repository`). The OpenRouter adapter is
the only place that imports `httpx` and reads the API key. The `shell/` composition root wires
the real adapter; tests wire `FakeLLMProvider`. Dependency direction: `shell → agent core →
ports`; the core never imports the adapter. Block 1's `engine/`/`config/`/`data/` are reused
unchanged; `query_gl_detail` resolves a reporting line to GL accounts via the Block 1 COA config.

## Complexity Tracking

> No constitution violations. No entries required.
