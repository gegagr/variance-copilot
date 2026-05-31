---
description: "Task list for As-of Period Selector (current_period single source of truth)"
---

# Tasks: As-of Period Selector

**Input**: Design documents from `specs/005-as-of-period-selector/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: INCLUDED — the user's rules mandate test-first for the review-store key change and the
seeding, plus API and frontend behavior tests. All tests run offline/deterministically (backend:
`FakeLLMProvider` + `InMemoryReviewStore` / temp SQLite; frontend: Vitest + RTL + MSW). No live API,
no LLM key.

**Organization**: Tasks are grouped by user story (P1–P3 from spec.md). The user's dependency order
(store re-key test-first → thread API → API tests → UI selector → query keys → frontend tests) is
honored across the phases below. This **extends** existing Block 4 + Block 5 files — no new screens,
no parallel endpoints, no duplicate components.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US3 (user-story phases only)
- Backend paths under `data/`, `api/`, `tests/`; frontend under `web/`.

## Path Conventions

Existing hexagonal backend (`engine/` pure, `api/` driving adapter, `data/` ports+adapters) and an
existing TanStack-Query SPA (`web/`). The engine is **untouched** — it already takes `current_period`.
The work is to make `current_period` an explicit, single source of truth at every other layer and key
review state by `(current_period, flag_id)`.

---

## Phase 1: Setup

**Purpose**: No new tooling — confirm the working tree is green before re-keying anything.

- [x] T001 Run `uv run pytest -q` and `cd web && npm test` to confirm the existing suites are green at HEAD (baseline before changes); note the current pass counts in the task PR description. No code change.

---

## Phase 2: Foundational — Review store re-keyed by `(current_period, flag_id)` (TEST-FIRST)

**Purpose**: Make per-period keying and idempotent seeding a property of the store + service. Blocking
prerequisite for US1 and US3.

**⚠️ CRITICAL**: Write T002–T003 (failing tests) BEFORE the implementation tasks T004–T008.

### Tests first (review store + seeding)

- [x] T002 [P] In `tests/test_review_store.py`, add failing tests for the period-aware port against `InMemoryReviewStore`: `upsert` an item under `(period=6, flag_id="f1")`, then `get(6,"f1")` round-trips and `get(5,"f1")` is `None`; `list_all(6)` returns only period-6 items; the same `flag_id` under periods 5 and 6 are two independent items with independent statuses; `actions_for(6,"f1")` returns only that pair's actions in insertion order.
- [x] T003 [P] In `tests/test_review_store.py`, add a failing SQLite test (temp path via `tmp_path`): round-trip an item per `(current_period, flag_id)` through `SqliteReviewStore`; assert composite-key isolation across periods; AND a "recreate-on-mismatch" test that pre-creates an OLD-schema `review_item` table (no `current_period` column) at the path, constructs `SqliteReviewStore`, and asserts it recreates and then reads/writes cleanly with the composite key.

### Implementation (review store)

- [x] T004 In `data/review_store.py`, add `current_period: int` to `ReviewItem` and to `ReviewAction` (see data-model.md); keep all other fields unchanged.
- [x] T005 In `data/review_store.py`, change the `ReviewStore` ABC signatures to be period-aware: `get(current_period, flag_id)`, `list_all(current_period)`, `actions_for(current_period, flag_id)`; `upsert(item)` and `append_action(action)` read `current_period` from the model (per contracts/review-store-port.md).
- [x] T006 In `data/review_store.py`, update `InMemoryReviewStore` to key items by the tuple `(current_period, flag_id)` and filter actions by `(current_period, flag_id)`; preserve deep-copy-on-read/write behavior. Make T002 pass.
- [x] T007 In `data/sqlite_review_store.py`, add a `current_period` (Integer, not null) column to `review_item` and `review_action`; make `review_item`'s primary key the composite `(current_period, flag_id)`; update the upsert to `on_conflict_do_update(index_elements=["current_period","flag_id"], …)`; filter `get`/`list_all`/`actions_for` by `current_period`; include `current_period` in `_row_to_item` and action reads.
- [x] T008 In `data/sqlite_review_store.py`, add recreate-on-mismatch: on construction, use SQLAlchemy `inspect` to detect an existing `review_item` table lacking the `current_period` column and, if found, drop+recreate the review tables before `create_all`. Make T003 pass. (git-ignored, mock-only DB — safe per research R3.)

**Checkpoint**: `uv run pytest tests/test_review_store.py -q` is green; store is fully period-aware.

---

## Phase 3 (US1 - P1): Review queue agrees with the grid for the chosen month 🎯 MVP

**Goal**: One user-selected `current_period` flows through the service and every endpoint, so the
P&L, variances, review queue, and progress all report the same flags for that month — and the queue
is non-empty at period 6.

**Independent Test**: `GET /review?current_period=6` is non-empty and lists exactly the flags
`GET /variances?current_period=6` reports; all four read endpoints agree for a given period.

### Service — remove the implicit session period (sequential; same file)

- [x] T009 [US1] In `api/services/review_service.py`, delete `self._session_period` and the `_session_*` helpers; add period-aware internals: `_pnl_for(current_period)` and reuse `_flags_for(current_period)`; `_ensure_item(current_period, flag)` and `_require(current_period, flag_id)` now key the store by the pair (per contracts/api-changes.md).
- [x] T010 [US1] In `api/services/review_service.py`, give every period-dependent method an explicit `current_period`: `get_pnl`, `get_pnl_view`, `get_flags` (seeds that period idempotently — only inserts missing items, never overwrites), `get_flags_view`, `investigate`, `answer`, `accept`, `edit`, `dismiss`; build the P&L/flags for the requested period via the engine (`load_config(current_period=…)`), look up/seed the `(current_period, flag_id)` item, transition, persist, and append a period-scoped `ReviewAction`. Construct NO figure.
- [x] T011 [US1] In `api/services/review_service.py`, make `progress(current_period)`, `accepted_commentary(current_period)`, and `history(flag_id, current_period)` period-scoped (progress counts resolved-of-total within that period only, using `store.list_all(current_period)`).
- [x] T012 [US1] In `api/services/review_service.py`, update `_record_action` to stamp `current_period` onto each `ReviewAction` it appends.

### Routes — thread `current_period` (no new endpoints; modify in place)

- [x] T013 [US1] In `api/routes/investigations.py`, add `current_period: int = Query(ge=1, le=12)` to `GET /review` (call `service.get_flags(current_period)` then return items for that period via `service.store.list_all(current_period)`), to `GET /review/{flag_id}` (use `service.store.get(current_period, flag_id)`), and to `POST /review/{flag_id}/investigate` and `POST /review/{flag_id}/answer` (pass `current_period` into the service). Remove the `service.config.settings.current_period` fallback.
- [x] T014 [US1] In `api/routes/review.py`, add `current_period: int = Query(ge=1, le=12)` to `GET /review/progress` (drop the session fallback), `GET /review/accepted`, `GET /review/{flag_id}/history`, and the `POST .../accept|edit|dismiss` routes; thread it into the service calls (update the `_act` helper to forward `current_period`).
- [x] T015 [US1] In `api/routes/pnl.py`, confirm `/pnl`, `/pnl/view`, `/variances`, `/variances/view` already pass the caller's `current_period` unchanged (no behavior change); adjust only if any default leaks. No new endpoints.

### Tests (US1) — consistency + non-empty queue

- [x] T016 [P] [US1] In a new `tests/test_api_as_of_period.py`, add: for `current_period=6` the flag-id set from `GET /variances`, `GET /review`, and `GET /review/progress` (total) are identical; uses `make_api_client(FakeLLMProvider([]))`.
- [x] T017 [P] [US1] In `tests/test_api_as_of_period.py`, assert `GET /review?current_period=6` is non-empty and returns one item per flagged variance for that as-of month — the FULL flag set (all time cuts + scenario pairs, matching `GET /variances?current_period=6`), NOT only current_month rows — and every item has `status=="detected"` on first access.
- [x] T018 [US1] Update existing API tests that called `/review`, `/review/progress`, history/accept/edit/dismiss without a period to pass `current_period=6` (`tests/test_api_investigations.py`, `tests/test_api_progress.py`, `tests/test_api_review_actions.py`, `tests/test_api_contract.py`); keep them green. (Sequential: touches several test files but each is independent — may be split.)

**Checkpoint**: `uv run pytest -q` green; all read endpoints agree for a period; queue non-empty @ P6.

---

## Phase 4 (US3 - P3): Per-month review work is preserved when switching months

**Goal**: Each as-of month owns its own queue and lifecycle state; acting in one month never touches
another, and first access to a new month seeds it without disturbing others.

**Independent Test**: Act on period 6 (accept one, dismiss one), seed/act on period 5, return to
period 6 — period 6 statuses unchanged; the same flag under period 5 is independent.

- [x] T019 [P] [US3] In `tests/test_api_as_of_period.py`, add a per-period isolation test: investigate+accept a flag under `current_period=6`, then `GET /review?current_period=5` (seeds period 5 fresh as `detected`), then re-GET `current_period=6` and assert the accepted item retained its status/content; assert the same `flag_id` under period 5 is `detected` (independent).
- [x] T020 [P] [US3] In `tests/test_api_as_of_period.py`, add an idempotent-seeding test: call `GET /review?current_period=6` twice and assert identical item count and statuses; then accept one item, GET again, and assert the accepted status is NOT reset (seeding never overwrites existing state).

**Checkpoint**: per-period isolation + idempotent seeding proven at the API level.

---

## Phase 5 (US2 - P2): Navigate the P&L across months (As-of selector + query-key threading)

**Goal**: An "As of" selector in the existing Workspace sets one `current_period` that all three
panes share through the TanStack Query keys; the existing time-cut selector still slices relative to
it. Reuse existing components — no new screens.

**Independent Test**: Changing the As-of selector refetches grid + variances + review for the new
month; the time-cut selector still works relative to the chosen as-of month.

### Constants + client + hooks (server-state seam)

- [x] T021 [US2] In `web/src/api/schema.ts`, replace `export const CURRENT_PERIOD = 6` with `export const DEFAULT_PERIOD = 6` (latest month with actuals) and `export const AS_OF_PERIODS = [1,2,3,4,5,6] as const` (months with actuals, latest last); update any import sites that referenced `CURRENT_PERIOD`.
- [x] T022 [US2] In `web/src/api/client.ts`, add `current_period` to the review/progress and mutation calls: `review(currentPeriod)`→`/review?current_period=…`, `progress(currentPeriod)`→`/review/progress?current_period=…`, and `investigate/answer/accept/edit/dismiss(flagId, currentPeriod[, body])`→append `?current_period=…`. `pnlView`/`variancesView` already take it.
- [x] T023 [US2] In `web/src/hooks/api.ts`, put `current_period` in every query key (`qk.pnl(p,tc)`, `qk.variances(p)`, `qk.review(p)`, `qk.progress(p)`) and give the hooks a `currentPeriod` param: `usePnl(p,tc)`, `useVariances(p)`, `useReview(p)`, `useProgress(p)`, `useReviewActions(p)`. Mutations carry `currentPeriod` and invalidate `qk.review(p)` + `qk.progress(p)` for that period.

### Workspace + selector component (reuse existing shell)

- [x] T024 [P] [US2] Create `web/src/components/AsOfSelector.tsx` mirroring `TimeCutSelector` (props `{ value: number; onChange: (p:number)=>void }`), rendering `AS_OF_PERIODS` with human labels (e.g. "Jun (P6)"); display-only, no figure math.
- [x] T025 [US2] In `web/src/components/Workspace.tsx`, add `const [currentPeriod, setCurrentPeriod] = useState<number>(DEFAULT_PERIOD)`; render `<AsOfSelector value={currentPeriod} onChange={setCurrentPeriod} />` in the header; thread `currentPeriod` into `usePnl/useVariances/useReview/useProgress/useReviewActions` and every mutation call; keep `TimeCutSelector` in the P&L pane slicing relative to `currentPeriod`.

### Frontend tests (MSW, offline)

- [x] T026 [US2] In `web/tests/msw/handlers.ts`, key the `/review`, `/review/progress`, `/pnl/view`, `/variances/view` fixtures by the `current_period` query param so each period returns its own deterministic data (period 6 → the seeded non-empty queue; another period → its own set).
- [x] T027 [P] [US2] Add `web/tests/asOfSelector.test.tsx`: render the Workspace, assert it defaults to the latest period and the queue populates for period 6; change the As-of selector to another period and assert the grid, variances, and review queue all refetch (request URLs carry the new `current_period`).
- [x] T028 [P] [US2] Add a test (in `web/tests/asOfSelector.test.tsx`) that the time-cut selector still switches the P&L cut while the as-of period is held fixed (independent controls); and that the existing no-arithmetic guard (`web/tests/noArithmetic.test.ts`) still passes (the selector adds no figure math).

**Checkpoint**: `cd web && npm test` green; switching the As-of period refetches all three panes.

---

## Phase 6: Polish & Cross-Cutting

- [x] T029 [P] Update `specs/005-as-of-period-selector/quickstart.md` only if any endpoint/param name drifted during implementation (keep curl examples accurate).
- [x] T030 Regenerate `web/src/api/types.ts` from the updated `/openapi.json` (the review/progress/mutation routes gained `current_period`) and fix any type drift in the client/hooks; do not hand-edit the generated file.
- [x] T031 Run the full suites once more (`uv run pytest -q`; `cd web && npm test`) and clean dev artifacts (`build/review.db`, `build/agent_audit.jsonl`); confirm Block 1 numbers untouched (engine/reconciliation tests green).

---

## Dependencies & Execution Order

- **Phase 1 (Setup)** → **Phase 2 (Foundational store, TEST-FIRST)** blocks everything.
- **US1 (Phase 3)** depends on Phase 2 (period-aware store). This is the **MVP** — delivers the bug fix.
- **US3 (Phase 4)** depends on Phase 2 + US1 (store + API threading); adds isolation/idempotency tests.
- **US2 (Phase 5)** depends on US1 (the API must accept `current_period` everywhere before the UI sends it).
- **Phase 6 (Polish)** last.

Story independence: once Phase 2 lands, US1 is independently testable at the API; US3 adds API-level
isolation tests; US2 is the UI layer over the threaded API. US2 can begin as soon as US1's routes
(T013–T015) are merged, in parallel with US3's tests.

## Parallel Execution Examples

- Phase 2 tests: T002 and T003 in parallel (different store adapters, same file — coordinate edits or split).
- US1 tests: T016 and T017 in parallel (same new file, independent test fns); T018 touches separate existing test files.
- US3: T019 and T020 in parallel (independent test fns).
- US2: T024 (new AsOfSelector file) in parallel with T021–T023 (client/hooks/schema); T027 and T028 in parallel after T025–T026.

## Implementation Strategy

- **MVP = Phase 1 + Phase 2 + US1 (Phase 3)**: the empty-queue bug is fixed and all read endpoints
  agree for one user-selected period. Ship/verify here first.
- **Increment 2 = US3 (Phase 4)**: prove per-period isolation + idempotent seeding (mostly tests over
  the Phase-2 store).
- **Increment 3 = US2 (Phase 5)**: the As-of selector + query-key threading so a user can actually
  navigate months in the UI.
- **Finish = Phase 6**: regen types, refresh docs, full green, artifacts cleaned. Block 1 untouched.
