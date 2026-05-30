---

description: "Task list for Review API Layer (Block 4)"
---

# Tasks: Review API Layer (Block 4)

**Input**: Design documents from `specs/003-review-api/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: INCLUDED — the spec and the user's sequencing rules mandate test-first for the
lifecycle state machine and for the "API performs no arithmetic on returned figures" guarantee.
All API tests run offline/deterministically via FastAPI `TestClient` + Block 3's
`FakeLLMProvider` (no network, no live LLM).

**Organization**: Tasks are grouped by user story (P1–P5 from spec.md). The user's dependency
order (review store → lifecycle test-first → schemas → service → routes → composition root →
integration) is honored within and across the phases below; each task lists its dependencies.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US5 (user-story phases only)
- All paths are repository-root relative.

## Path Conventions

Adds the `api/` package (FastAPI driving adapter + `services/` application layer) plus
`data/review_store.py` + `data/sqlite_review_store.py` and `config/api_settings.py`. Routes are
thin; workflow lives in `api/services/`; **no financial logic anywhere in this layer**. Reuses
Block 1 (`engine/`, `config/`, `data/`) and Block 3 (`agent/`) unchanged.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependencies and scaffolding for the API layer.

- [x] T001 Add `fastapi`, `uvicorn[standard]`, `sqlalchemy>=2` to `[project].dependencies` in `pyproject.toml` (`httpx` already present); run `uv sync`
- [x] T002 Create the `api/` package (`api/__init__.py`, `api/routes/__init__.py`, `api/services/__init__.py`) per plan.md structure
- [x] T003 [P] Define `APISettings` (sqlite_path default `build/review.db`, cors_origin, controller_id) in `config/api_settings.py` with an env/CSV loader
- [x] T004 [P] Confirm `.gitignore` excludes the SQLite review DB (`build/` already ignored; add `*.db` / `review.db`)

---

## Phase 2: Foundational — Review store + lifecycle (Blocking Prerequisites)

**Purpose**: The persistence foundation and the state machine that every user story depends on.
Ordered per the user's rules: review schema + store FIRST, then the lifecycle state machine
TEST-FIRST.

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

### Review schema + ReviewStore port + SQLite adapter (foundation)

- [x] T005 Define `ReviewStatus`, `ReviewActionType`, and the domain models `ReviewItem` and `ReviewAction` (with embedded Block 3 contract snapshots) in `data/review_store.py` per data-model.md
- [x] T006 Define the `ReviewStore` ABC (`get`, `upsert`, `list_all`, `append_action`, `actions_for`) in `data/review_store.py` per contracts/review_store.md (depends on T005)
- [x] T007 Implement `SqliteReviewStore` (SQLAlchemy tables `review_item`, `review_action`; contracts stored as JSON columns; creates tables if absent) in `data/sqlite_review_store.py` (depends on T006)
- [x] T008 [P] Implement an `InMemoryReviewStore` test double satisfying the same port in `data/review_store.py` (depends on T006)
- [x] T009 [P] Review-store tests: upsert/get round-trip (incl. embedded contract snapshots); append/read action order; `list_all`; and **persistence across a simulated restart** (close + re-open `SqliteReviewStore` at the same path) in `tests/test_review_store.py` (depends on T007)

### Lifecycle state machine — TEST-FIRST

- [x] T010 [P] Lifecycle tests (write first, MUST fail): every VALID `(status, action)` transition returns the expected new status; every INVALID one (e.g. accept while awaiting_controller, investigate while accepted, answer while drafted) raises `InvalidTransition`; resolved == {accepted, dismissed}; edit-on-accepted → drafted; re-investigate only from detected/drafted, in `tests/test_lifecycle.py`
- [x] T011 Implement the declarative state machine `transition(status, action) -> new_status` (table per contracts/lifecycle.md) and `InvalidTransition` in `api/services/lifecycle.py`; make T010 pass (depends on T005, T010)

**Checkpoint**: Durable review store (with restart-safe persistence) and a tested state machine
exist — the service and stories can build on them.

---

## Phase 3: User Story 1 - Serve the P&L and flagged variances (Priority: P1) 🎯 MVP

**Goal**: Serve the engine P&L for a period/time cut and the Block 1 flagged variances, verbatim
— the API recomputes nothing.

**Independent Test**: Request the P&L and flags; confirm figures are byte-identical to the
engine's own output for the same inputs/config, and the API performs no arithmetic.

### Tests for User Story 1 ⚠️ (write first, must fail)

- [x] T012 [P] [US1] Pass-through / NO-ARITHMETIC test: every figure in `GET /pnl` and `GET /variances` equals the engine's own `build_pnl` / `flag_variances` output (deep model equality), and a static check confirms `api/routes/` and `api/services/` contain no arithmetic on figure fields, in `tests/test_api_pnl.py`

### Implementation for User Story 1

- [x] T013 [US1] Define pass-through response DTOs (`PnLView`, `FlagsView`) reusing `PnLResult` / `FlaggedVariance` verbatim in `api/schemas.py`
- [x] T014 [US1] Implement `ReviewService.get_pnl(current_period, time_cut)` and `get_flags(current_period)` as pure pass-throughs (no figure constructed) in `api/services/review_service.py` (depends on T013)
- [x] T015 [US1] Implement thin routes `GET /pnl` and `GET /variances` (validate query params; 404 on unknown period) in `api/routes/pnl.py` (depends on T014)

**Checkpoint**: P&L + flags served verbatim — MVP read-through, no recompute.

---

## Phase 4: User Story 2 - Run and serve investigations with progressive status (Priority: P2)

**Goal**: Trigger the Block 3 agent per variance (offline via fake provider); the variance moves
detected → investigating → awaiting-controller (Question) or drafted (Draft); a fail-safe returns
it to detected and serves no commentary.

**Independent Test**: Trigger an investigation with the fake provider; confirm the status
transitions and the served `InvestigationRecord` equals Block 3's output; a fail-safe leaves the
variance non-drafted and surfaces the failure.

### Tests for User Story 2 ⚠️ (write first, must fail)

- [x] T016 [P] [US2] Investigation tests (TestClient + `FakeLLMProvider` via `dependency_overrides`): `POST /review/{id}/investigate` → awaiting_controller (Question) or drafted (Draft); record served verbatim; fail-safe → detected with a failure signal and no commentary; re-investigate allowed from drafted (resets provenance), rejected (409) from awaiting_controller; and an `investigate` `ReviewAction` (actor + ts) is appended (FR-013), in `tests/test_api_investigations.py`

### Implementation for User Story 2

- [x] T017 [US2] Add `ReviewItemView` DTO (status + reused `InvestigationRecord`/`Draft`/`ControllerInput`) in `api/schemas.py`
- [x] T018 [US2] Implement `ReviewService.investigate(flag_id, *, now)`: apply lifecycle (detected/drafted → investigating); on a re-run from drafted, reset `original_draft` and clear `edited_text` (fresh provenance); run Block 3 `investigate(...)`, persist record + status (awaiting_controller | drafted | detected on fail-safe), append a `ReviewAction`, in `api/services/review_service.py` (depends on T011, T007, T017)
- [x] T019 [US2] Implement routes `POST /review/{flag_id}/investigate`, `GET /review`, `GET /review/{flag_id}` (404 unknown; 409 invalid transition) in `api/routes/investigations.py` (depends on T018)

**Checkpoint**: Investigations run per variance with progressive status, served verbatim.

---

## Phase 5: User Story 3 - Answer a question and receive the draft (Priority: P3)

**Goal**: Submit a controller answer for an awaiting-controller variance; Block 3 drafts; the
variance moves to drafted with the Draft served and provenance recording the answer.

**Independent Test**: For an awaiting-controller variance, submit an answer; confirm a Draft is
returned whose provenance records the answer and whose figures trace to source (Block 3
guarantee), and status becomes drafted; answering a non-awaiting variance is rejected (409).

### Tests for User Story 3 ⚠️ (write first, must fail)

- [x] T020 [P] [US3] Answer tests (TestClient + fake provider): `POST /review/{id}/answer` on awaiting_controller → drafted with Draft + answer in provenance; answer on a non-awaiting variance → 409, in `tests/test_api_investigations.py::answer`

### Implementation for User Story 3

- [x] T021 [US3] Add `AnswerRequest` DTO in `api/schemas.py`
- [x] T022 [US3] Implement `ReviewService.answer(flag_id, answer, *, now)`: lifecycle awaiting_controller → drafted, call Block 3 `draft_from_controller(...)`, persist `original_draft` + record, append `ReviewAction`, in `api/services/review_service.py` (depends on T018, T021)
- [x] T023 [US3] Implement route `POST /review/{flag_id}/answer` (thin) in `api/routes/investigations.py` (depends on T022)

**Checkpoint**: Question → answer → draft closes the loop, with provenance.

---

## Phase 6: User Story 4 - Accept, edit, or dismiss a draft (Priority: P4)

**Goal**: Accept makes commentary final; edit preserves the original AI draft + edited text and
(if accepted) reverts to drafted requiring re-accept; dismiss removes the variance. Every action
is audited.

**Independent Test**: From drafted, exercise accept/edit/dismiss; confirm status transitions,
edit retains original + edited text, editing an accepted item reverts to drafted, nothing is
final without accept, and every action records actor + timestamp.

### Tests for User Story 4 ⚠️ (write first, must fail)

- [x] T024 [P] [US4] Review-action tests (TestClient): accept (drafted→accepted; final only then); edit (drafted→drafted, both texts retained; accepted→drafted re-accept required); dismiss (→dismissed, excluded from accepted set); invalid actions → 409; each action appends a `ReviewAction` with actor + ts, in `tests/test_api_review_actions.py`

### Implementation for User Story 4

- [x] T025 [US4] Add `EditRequest` DTO in `api/schemas.py`
- [x] T026 [US4] Implement `ReviewService.accept / edit / dismiss(flag_id, ..., *, now)`: apply lifecycle (incl. edit-on-accepted → drafted), retain `original_draft`, write `edited_text`, append a `ReviewAction` for each, in `api/services/review_service.py` (depends on T011, T022)
- [x] T027 [US4] Implement routes `POST /review/{flag_id}/accept|edit|dismiss` and `GET /review/{flag_id}/history` (thin) in `api/routes/review.py` (depends on T026)

**Checkpoint**: The Human-in-the-Loop core works end to end with audit + provenance.

---

## Phase 7: User Story 5 - Review progress and accepted commentary in layout order (Priority: P5)

**Goal**: Serve resolved-vs-total progress and the accepted commentary ordered by P&L layout,
excluding dismissed, ready for the report layer.

**Independent Test**: With a known mix of statuses, confirm resolved == accepted + dismissed over
total, and the accepted set is returned in P&L-layout order with provenance, excluding dismissed.

### Tests for User Story 5 ⚠️ (write first, must fail)

- [x] T028 [P] [US5] Progress + accepted-set tests (TestClient): `GET /review/progress` resolved == accepted + dismissed / total; `GET /review/accepted` ordered by reporting-line layout order, dismissed excluded, provenance present, in `tests/test_api_progress.py`

### Implementation for User Story 5

- [x] T029 [US5] Add `ReviewProgressView` + `AcceptedCommentaryItem` DTOs in `api/schemas.py`
- [x] T030 [US5] Implement `ReviewService.progress()` and `accepted_commentary()` (order by the Block 1 layout `order`; text = edited else draft; carry provenance) in `api/services/review_service.py` (depends on T026)
- [x] T031 [US5] Implement routes `GET /review/progress` and `GET /review/accepted` (thin) in `api/routes/review.py` (depends on T030)

**Checkpoint**: Progress and the assembled accepted set are served in layout order.

---

## Phase 8: Composition root, CORS & contract (Cross-Cutting — last)

**Purpose**: Wire the FastAPI app and prove the offline test seam + the documented contract.

- [x] T032 Implement FastAPI dependency providers (`get_config`, `get_repository`, `get_gl_repository`, `get_agent_settings`, `get_provider`, `get_review_store`) in `api/deps.py` (depends on T007, T030)
- [x] T033 Implement `api/main.py`: build the FastAPI app, include routers, enable CORS for `APISettings.cors_origin`, wire the composition root (fixture Repository + engine + agent + SqliteReviewStore); expose `/docs` (depends on T015, T019, T023, T027, T031, T032)
- [x] T034 [P] Add a `conftest` fixture/helper that builds a `TestClient` with `app.dependency_overrides` → `FakeLLMProvider` + a temp-file SQLite store (offline) in `tests/conftest.py`
- [x] T035 [P] Contract test: response shapes match the documented schemas / published OpenAPI for every endpoint; error model (404/409/422) behaves per contracts/openapi-outline.md, in `tests/test_api_contract.py` (depends on T033)
- [x] T036 [P] Architecture guard test: `api/routes/` contain no workflow/financial logic (delegate to the service); `api/services/` never import `fastapi`; and neither `api/routes/` nor `api/services/` constructs commentary text — every served Question/Draft `text`/`commentary` originates from a Block 3 object (FR-007), in `tests/test_api_architecture.py`

---

## Phase 9: Polish

- [x] T037 [P] Document the live run + the endpoints in `README.md`; add a Block 4 SC traceability note (SC-001…SC-010 → tests) to `tests/README.md`
- [x] T038 [P] Validate every command in `quickstart.md` runs (offline service path + TestClient; live path documented but key-gated)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories. Internal order: review
  schema + store (T005→T006→T007, +T008/T009) → lifecycle TEST-FIRST (T010 → T011).
- **User Stories (Phases 3–7)**: depend on Foundational. US1 (read-through) is independent; US2
  (investigate) → US3 (answer) → US4 (accept/edit/dismiss) → US5 (progress/accepted) form the
  workflow pipeline; each is independently testable.
- **Composition root (Phase 8)**: after the routes/services exist; the `TestClient` seam (T034)
  enables the integration/contract tests.
- **Polish (Phase 9)**: last.

### Critical-path note (honoring the user's sequencing)

```
store(T005→T007) → LIFECYCLE test-first(T010)→impl(T011)
   → schemas(T013,T017,T021,T025,T029) → service(T014,T018,T022,T026,T030)
       → routes(T015,T019,T023,T027,T031) → composition root + CORS(T032,T033)
           → integration/contract tests(T034,T035,T036)
```

### Parallel Opportunities

- Setup: T003, T004 in parallel.
- Foundational: T008, T009 alongside each other; T010 (lifecycle tests) in parallel with the
  store work (different files), before T011.
- Per-story test tasks (T012, T016, T020, T024, T028) run in parallel (separate files), each
  before its story's implementation.
- Schema DTO additions touch `api/schemas.py` (shared file) → sequence T013/T017/T021/T025/T029.
- Service methods touch `api/services/review_service.py` (shared) → sequence
  T014/T018/T022/T026/T030.
- Phase 8/9: T034, T035, T036, T037, T038 largely parallel after T033.

---

## Parallel Example: Foundational

```bash
# After T006 (the port), launch together:
Task: "Implement SqliteReviewStore in data/sqlite_review_store.py"     # T007
Task: "Implement InMemoryReviewStore double in data/review_store.py"   # T008
Task: "Write lifecycle transition tests in tests/test_lifecycle.py"    # T010 (must fail first)
```

---

## Implementation Strategy

### MVP First (Foundational + User Story 1)

1. Phase 1 Setup → 2. Phase 2 Foundational (store + lifecycle) → 3. Phase 3 US1
(P&L + flags pass-through). **STOP and VALIDATE**: the API serves the engine's P&L and flags
verbatim, with the no-arithmetic guarantee proven. A client can already render the table.

### Incremental Delivery

1. Setup + Foundational → durable store + tested lifecycle.
2. US1 → P&L + flags (read-through, MVP).
3. US2 → per-variance investigations with progressive status.
4. US3 → answer → draft.
5. US4 → accept / edit / dismiss (Human-in-the-Loop core).
6. US5 → progress + accepted commentary in layout order.
7. Composition root + CORS + integration/contract tests → the documented UI contract.

Each increment is independently testable and adds value without breaking the prior.

---

## Notes

- `[P]` = different files, no incomplete dependencies. Tasks touching `api/schemas.py`
  (T013/T017/T021/T025/T029) and `api/services/review_service.py`
  (T014/T018/T022/T026/T030) share files and are intentionally NOT `[P]` among themselves.
- Tests precede implementation for the lifecycle (T010) and the no-arithmetic guarantee (T012),
  and for each story. All API tests use `TestClient` + `FakeLLMProvider` — offline, deterministic.
- Constitution guards: T012 (no arithmetic on figures), T036 (no workflow/financial logic in
  routes; service free of FastAPI), T010/T011 (explicit lifecycle; invalid transitions rejected),
  T024 (nothing final without accept; provenance retained), T009 (durable persistence),
  per-action audit in T018/T022/T026.
- No task introduces real data connectors; the fixture Repository is used throughout. Commit
  after each task or logical group; stop at any checkpoint.
