---

description: "Task list for AI Investigation and Commentary Layer (Block 3)"
---

# Tasks: AI Investigation and Commentary Layer (Block 3)

**Input**: Design documents from `specs/002-ai-investigation-commentary/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: INCLUDED — the spec and the user's sequencing rules mandate test-first for the
traceability guard and the agent loop, with a `FakeLLMProvider` so the suite is deterministic
and offline (no network, no API key).

**Organization**: Tasks are grouped by user story (P1–P4 from spec.md). The user's dependency
order (contracts → ports → fake provider → guard test-first → loop → commentary → audit →
OpenRouter adapter → shell) is honored *within and across* the phases below; each task lists its
explicit dependencies.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US4 (user-story phases only)
- All paths are repository-root relative.

## Path Conventions

Adds the `agent/` package to the Block 1 project (ports-and-adapters). Agent core
(`investigate.py`, `commentary.py`, `guards.py`, `models.py`) contains **no SDK/HTTP calls**;
only `agent/provider.py`'s `OpenRouterProvider` imports `httpx`/reads the API key. Block 1
`engine/`, `config/`, `data/` are reused unchanged.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Package scaffolding and dependencies for the agent layer.

- [x] T001 Create the `agent/` package (`agent/__init__.py`) and add the `shell/investigate_pipeline.py` placeholder per plan.md structure
- [x] T002 Add `httpx>=0.27` to `[project].dependencies` and `jsonschema` is already a dev dep; run `uv sync` to update the environment
- [x] T003 [P] Confirm `.gitignore` excludes `.env`/API keys and `build/` (already present from Block 1); add `OPENROUTER_API_KEY` to a `.env.example` (no real key)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Contracts, ports, fixtures, and the fake provider — everything the agent logic and
its offline tests depend on. Ordered per the user's rules: contracts → ports → fake provider.

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

### Contracts first (data models + versioned schemas)

- [x] T004 Define enums (`RecordStatus`, `AggregateOp`, `FigureSource`) and the evidence/figure models (`GLEvidenceRow`, `GLQuery`, `GLQueryResult`, `AggregateSpec`, `RenderedFigure`, `Hypothesis`, `ControllerInput`, `DraftProvenance`) in `agent/models.py` per data-model.md
- [x] T005 Define the versioned output contracts `Question`, `Draft`, and `InvestigationRecord` (with `schema_version: Literal["1.0.0"]`, embedded evidence snapshots, `is_proposal=True` on Draft) in `agent/models.py` (depends on T004)
- [x] T006 [P] Verify the committed JSON Schemas `contracts/question.schema.json`, `contracts/draft.schema.json`, `contracts/investigation_record.schema.json` match the models; add a `schema_export` check helper in `agent/models.py` (depends on T005)

### Ports next (interfaces + GL tool)

- [x] T007 [P] Define the `LLMProvider` port (Protocol) and `ProviderResponse` types (`ToolCall`, `StructuredFinal`) in `agent/provider.py` per contracts/llm_provider.md — interface only, no adapter yet (depends on T004)
- [x] T008 Define the `query_gl_detail` tool — JSON tool schema + Python impl bound to the Block 1 `Repository`/`EngineConfig`, resolving `reporting_line → GL accounts` via COA and returning `GLEvidenceRow`s — in `agent/tools.py` (depends on T004)

### Enriched fixtures + config

- [x] T009 [P] Create enriched mock GL fixtures with `date`, `counterparty`, `labels` (e.g. `sample/gl_detail.csv` or augment `sample/transactions_*.csv`) and extend `FixtureRepository`/the tool to surface these fields — mock data only (Principle VIII)
- [x] T010 [P] Define `AgentSettings` (`model_id`, `temperature`, `max_tool_calls_per_variance`, `dominant_share_threshold`) in `config/agent_settings.py` and a mock `config/agent_settings.csv`; load via the config loader

### Fake provider before the real adapter

- [x] T011 Implement `FakeLLMProvider` (scripted `ToolCall`/`StructuredFinal` sequence) plus `tool_call(...)`/`final(...)` helpers in `agent/fakes.py`, so all downstream logic is testable offline (depends on T007)
- [x] T012 [P] Contract test for `query_gl_detail` (correct rows per line/period/scenario; subtotal returns union of component accounts; filters narrow; read-only) in `tests/test_query_gl_detail.py` (depends on T008, T009)

**Checkpoint**: Contracts, ports, fixtures, config, and the fake provider exist — agent logic
and its offline tests can begin.

---

## Phase 3: The Traceability Guard (TEST-FIRST — the constitution's hard line)

**Purpose**: The deterministic guard that makes "the LLM never produces a number" true. Built
**before** the commentary stories because T025 BLOCKS US2 (T019) and US3 (T023). Test-first with
adversarial cases.

### Tests first ⚠️ (write first, must fail)

- [x] T029 [P] Guard tests — happy path: every number in rendered text equals a verbatim source value (Block 1 figure or GL amount) or a recomputed aggregate → passes, in `tests/test_guards.py`
- [x] T030 [P] Guard tests — ADVERSARIAL: a number absent from all sources is rejected; a disguised figure (currency symbol, thousands separators, percentage) is normalized and checked; an aggregate that does not recompute is rejected; a raw digit outside a token fails `assert_no_raw_digits`, in `tests/test_guards.py`

### Implementation

- [x] T025 Implement the deterministic guard in `agent/guards.py`: `assert_no_raw_digits(tokenized_text)`, number extraction + `Decimal` normalization (currency/sign/grouping/percentage), code-computed aggregate recomputation, and `assert_grounded(text, allowed) -> GuardResult`; reject (don't emit) on any unmatched number (depends on T004; MUST pass T029/T030; BLOCKS T019, T023)

**Checkpoint**: The guard passes its adversarial suite and gates all commentary output.

---

## Phase 4: User Story 1 - Investigate a flagged variance and gather grounded evidence (Priority: P1) 🎯 MVP

**Goal**: Run the investigation loop — given a flag + P&L context and the injected ports, the
agent calls `query_gl_detail`, gathers evidence, forms a hypothesis, and emits one
`InvestigationRecord` (status Question or Draft) — all offline with the fake provider.

**Independent Test**: Drive `investigate(...)` with a `FakeLLMProvider` scripted to call
`query_gl_detail` then emit a structured record; assert the GL query is scoped to the flag, the
record embeds the actual returned rows, the hypothesis names those rows, and status ∈
{question, draft}; sparse evidence → null hypothesis + Question.

### Tests for User Story 1 ⚠️ (write first, must fail)

- [x] T013 [P] [US1] Contract test for `InvestigationRecord` (validates against `investigation_record.schema.json`; one record per flag; status/question/draft consistency) in `tests/test_contract_investigation.py`
- [x] T014 [P] [US1] End-to-end loop test with `FakeLLMProvider` exercising a `query_gl_detail` call: evidence embedded, hypothesis grounded, status set, sparse-evidence → open Question with null hypothesis, in `tests/test_investigate_loop.py`

### Implementation for User Story 1

- [x] T015 [US1] Implement the investigation loop `investigate(flag, pnl, *, provider, gl_tool, settings, audit, now) -> InvestigationRecord` — provide variance context + tools, run the bounded tool-call loop, gather evidence, apply the `dominant_share_threshold` self-explanatory-vs-question policy — in `agent/investigate.py` (depends on T005, T007, T008, T010, T011)
- [x] T016 [US1] Enforce the bound `max_tool_calls_per_variance` and the one-record-per-flag invariant; handle sparse/empty evidence (null hypothesis, status Question) in `agent/investigate.py` (depends on T015)

**Checkpoint**: The loop produces grounded InvestigationRecords offline — MVP of the agent.

---

## Phase 5: User Story 2 - Pose a specific, evidence-grounded question (Priority: P2)

**Goal**: When status is Question, assemble a `Question` that states the hypothesis, references
specific evidence, and (on sparse evidence) is open and honest — with every figure rendered by
code, never typed by the model.

**Independent Test**: For an ambiguous flag, the emitted Question references specific evidence
rows and states the hypothesis and is not generic; for sparse evidence, it is an open question
asserting no invented cause; every number in the text traces to a source value.

### Tests for User Story 2 ⚠️ (write first, must fail)

- [x] T017 [P] [US2] Contract test for `Question` (schema validation; references ≥1 evidence row; not a generic template; sparse → open question) in `tests/test_contract_question.py`
- [x] T018 [P] [US2] Grounding test: a Question whose model output contains a raw digit, or a figure token resolving to a non-source value, is rejected, in `tests/test_commentary.py::question` (depends on the Phase 3 guard, T025)

### Implementation for User Story 2

- [x] T019 [US2] Implement Question assembly in `agent/commentary.py`: take the structured model output (hypothesis + tokenized text + cited row ids), render figure tokens to values, build the `Question` with `rendered_figures` and `llm_log_refs` (depends on T015, and the guard T025)
- [x] T020 [US2] Implement the open/honest question path for null-hypothesis (sparse evidence) cases in `agent/commentary.py` (depends on T019)

**Checkpoint**: Grounded and open questions are produced and guard-validated.

---

## Phase 6: User Story 3 - Draft management commentary from confirmed input (Priority: P3)

**Goal**: For a self-explanatory variance, or once a `ControllerInput` is supplied for a
Question, draft a concise commentary line combining the confirmed explanation with the evidence,
recording full provenance. Every figure is code-rendered.

**Independent Test**: Given a Draft-status record (or a Question-status record + fixture
controller response), the emitted `Draft` reflects the evidence/confirmed explanation, its
provenance names variance + evidence + controller input, `is_proposal` is true, and every number
traces to a source value or recomputed aggregate.

### Tests for User Story 3 ⚠️ (write first, must fail)

- [x] T021 [P] [US3] Contract test for `Draft` (schema validation; provenance present; `is_proposal=True`; not finalized) in `tests/test_contract_draft.py`
- [x] T022 [P] [US3] Drafting tests: self-explanatory → Draft with no question and empty controller input; Question + controller response → Draft reflecting the response; drafting gated on a response for Question-status records, in `tests/test_commentary.py::draft`

### Implementation for User Story 3

- [x] T023 [US3] Implement `render_draft(spec, evidence, allowed, *, controller_input) -> Draft` in `agent/commentary.py`: render figure tokens (incl. code-computed aggregates), assemble commentary + `DraftProvenance` + `rendered_figures` + `llm_log_refs`, set `is_proposal=True` (depends on T019, T025)
- [x] T024 [US3] Gate drafting on a `ControllerInput` for Question-status records; for self-explanatory records draft directly with null controller input, in `agent/investigate.py`/`agent/commentary.py` (depends on T023)
- [x] T037 [US3] Implement bounded retry on guard rejection (research R3 / FR-015): when `assert_grounded` rejects a rendered Question/Draft, re-prompt the provider up to a configured bound, then fail safe; test a first-bad/second-good fake sequence yields a valid output and first-bad/second-bad emits none, in `agent/investigate.py` + `tests/test_investigate_loop.py` (depends on T025, T019, T023)

**Checkpoint**: Drafts are produced with provenance, gated correctly, guard-validated, and a bounded retry recovers from a single ungrounded generation.

---

## Phase 7: User Story 4 - Audit every LLM interaction (Priority: P4)

**Goal**: Log every LLM interaction (prompt, response, model id, timestamp) to JSON lines with
the API key redacted, and link each Question/Draft to its originating log entry.

**Independent Test**: Run an investigation that calls the model; assert one log entry per call
with ts/model/request/response, the API key absent, and each emitted Question/Draft carrying the
log entry id(s).

### Tests for User Story 4 ⚠️ (write first, must fail)

- [x] T026 [P] [US4] Audit tests: one JSON-lines entry per LLM call with `ts`/`model`/`request`/`response`; API key never present; outputs carry `llm_log_refs`, in `tests/test_audit.py`

### Implementation for User Story 4

- [x] T027 [US4] Implement the JSON-lines audit log in `agent/audit.py`: append-per-call with caller-supplied `now` timestamp (deterministic), redact the API key, return entry ids for `llm_log_refs` (depends on T004)
- [x] T028 [US4] Wire `audit` into the investigation loop and commentary so every call is logged and every output links to its entry id(s) in `agent/investigate.py`, `agent/commentary.py` (depends on T027, T015, T023)
- [x] T036 [US4] Implement fail-safe handling (FR-019): when the provider errors/ is unavailable or returns malformed/unvalidatable structured output, record the failure in the audit log and emit NO ungrounded question/draft (no record, or a `failed`-status record); test with a `FakeLLMProvider` that raises and one that returns malformed output, in `agent/investigate.py` + `tests/test_investigate_loop.py` (depends on T015, T027)

**Checkpoint**: Full interaction audit trail with output→log linkage, and safe-fail on provider/parse failure.

---

## Phase 8: Real OpenRouter Adapter (last, behind the port)

**Purpose**: The only network/SDK site, added after all logic is proven offline.

- [x] T031 Implement `OpenRouterProvider(LLMProvider)` in `agent/provider.py` using `httpx`, reading `OPENROUTER_API_KEY` from the environment, translating messages+tools to/from the OpenRouter API, parsing into `ToolCall`/`StructuredFinal` (depends on T007)
- [x] T032 [P] Architecture guard test: only `agent/provider.py` imports `httpx`/reads `OPENROUTER_API_KEY`; the agent core (`investigate.py`, `commentary.py`, `guards.py`, `models.py`, `tools.py`) contains no SDK/HTTP calls and no LLM key access, in `tests/test_agent_architecture.py`

**Checkpoint**: A real model is reachable behind the same port; the core remains SDK-free.

---

## Phase 9: Shell Wiring & Polish (last)

**Purpose**: Wire Block 3 onto Block 1's flagged variances as a CLI step, plus cross-cutting docs.

- [x] T033 Implement `shell/investigate_pipeline.py`: run Block 1 (`build_pnl → compute_variances → flag_variances`), construct `OpenRouterProvider` + `query_gl_detail` from config, run `investigate(...)` per flag, write `InvestigationRecord`s to `build/investigations.jsonl` and the audit log (depends on T015, T024, T028, T031)
- [x] T034 [P] Add a Success-Criteria traceability note (SC-001…SC-008 → covering tests) to `tests/README.md` and document the live run in the project `README.md`
- [x] T035 [P] Validate every command in `quickstart.md` runs (the offline core path with the fake provider; the live path documented but key-gated)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories. Internal order:
  contracts (T004→T005→T006) → ports (T007, T008) → fixtures/config (T009, T010) → fake provider
  (T011) → tool contract test (T012).
- **The Guard (Phase 3)**: test-first (T029, T030) then T025; **T025 BLOCKS US2 (T019) and US3
  (T023)** — placed before the commentary stories, per the user's rules.
- **User Stories**: US1 (loop, Phase 4) → US2 (questions, Phase 5, needs guard) → US3 (drafts,
  Phase 6, needs guard; +bounded retry T037) → US4 (audit + fail-safe, Phase 7, woven into loop +
  commentary). Pipeline order; each is independently testable.
- **OpenRouter adapter (Phase 8)**: after all logic is proven offline.
- **Shell (Phase 9)**: last; depends on the loop, drafting, audit, and the adapter.

### Critical-path note (honoring the user's sequencing)

```
contracts(T004,T005) → ports(T007,T008) → fake provider(T011)
        → GUARD test-first(T029,T030)→impl(T025)
            → loop(T015,T016) → questions(T019,T020) → drafts(T023,T024)
                → audit(T027,T028) → OpenRouter adapter(T031) → shell(T033)
```

### Parallel Opportunities

- Setup: T003 alongside T001/T002.
- Foundational: T006, T007, T009, T010 in parallel after T004/T005; T012 after T008/T009.
- Guard: T029, T030 in parallel (same file, but independent test funcs — write together).
- Per-story contract tests (T013, T017, T021, T026) run in parallel (separate files).
- Phase 8: T032 alongside T031. Phase 9: T034, T035 in parallel after T033.

---

## Parallel Example: Foundational contracts + ports

```bash
# After T004/T005 (agent/models.py), launch together:
Task: "Verify JSON Schemas match models in agent/models.py"        # T006
Task: "Define LLMProvider port in agent/provider.py"               # T007
Task: "Create enriched GL fixtures in sample/gl_detail.csv"        # T009
Task: "Define AgentSettings in config/agent_settings.py"           # T010
```

## Parallel Example: Guard test-first

```bash
Task: "Guard happy-path tests in tests/test_guards.py"             # T029
Task: "Guard adversarial tests in tests/test_guards.py"            # T030
# Both must FAIL before implementing T025.
```

---

## Implementation Strategy

### MVP First (Foundational + Guard + User Story 1)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 Guard (test-first) →
4. Phase 4 US1 (investigation loop). **STOP and VALIDATE**: the agent investigates a flag
offline and emits a grounded InvestigationRecord whose every number is code-rendered. This is the
constitutional heart proven end-to-end with the fake provider.

### Incremental Delivery

1. Foundational + Guard → grounding enforced.
2. US1 → investigation loop (records, evidence, hypothesis).
3. US2 → grounded/open questions.
4. US3 → drafts with provenance.
5. US4 → audit trail.
6. OpenRouter adapter → live model behind the port.
7. Shell → CLI over Block 1's flags.

Each increment is independently testable and adds value without breaking the prior.

---

## Notes

- `[P]` = different files, no incomplete dependencies. Tasks touching `agent/models.py` (T004,
  T005, T006), `agent/commentary.py` (T019, T020, T023, T024), and `agent/investigate.py` (T015,
  T016, T028) share files and are intentionally NOT `[P]` among themselves.
- The guard now sits in **Phase 3**, before the commentary stories that depend on it (T019/T023);
  its task id (T025) is higher than US1's ids but phase order, not id order, drives execution.
- T036 (fail-safe on provider/parse failure, FR-019) and T037 (bounded retry on guard rejection,
  R3/FR-015) are appended out of id sequence to preserve existing ids; they belong to US4 and US3
  respectively.
- Constitution guards: T025/T029/T030 (no LLM-produced numbers), T032 (no SDK in core),
  T026 (key never logged), T036 (no ungrounded emit on failure), T013/T017/T021 (versioned
  contracts), T028 (audit linkage).
- Tests precede implementation for the guard and each story. No task introduces a direct SDK call
  into the agent core. Commit after each task or logical group; stop at any checkpoint.
