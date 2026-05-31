# Phase 0 — Research & Decisions: As-of Period Selector

All NEEDS CLARIFICATION from the Technical Context are resolved below. Each item records the
decision, the rationale, and the alternatives rejected. The theme: **extend the existing seams,
make `current_period` explicit everywhere, and let the engine remain the only thing that computes.**

## R1 — Thread one `current_period` through every layer (the bug)

**Decision**: Remove `ReviewService._session_period`. Every service method that depends on the
as-of month (`get_flags`, `get_pnl`, `investigate`, `answer`, `accept`, `edit`, `dismiss`,
`progress`, `accepted_commentary`, `history`) takes `current_period` as an explicit argument. The
`/review` and `/review/progress` routes — which today pass `service.config.settings.current_period`
— instead accept `current_period` as a query parameter (validated `ge=1, le=12`), exactly like
`/pnl` and `/variances` already do. The mutation routes (investigate/answer/accept/edit/dismiss)
also take `current_period` so each action targets the correct per-period item.

**Rationale**: The empty-queue bug is a *split source of truth*: the grid reads the user's period
while the review routes read the API's configured default, and the store is period-blind. Today both
happen to default to 6, yet the queue still desynchronizes because the persisted store keys items by
`flag_id` only and survives across data/flag-id changes (see R3). Making the period an explicit,
single parameter — and routing the store by it (R2) — removes the split entirely: for any month the
P&L, variances, queue, and progress are computed from the *same* `current_period`.

**Alternatives rejected**:
- *Keep a session period, just sync the default*: brittle — re-introduces the same split the moment
  the UI offers more than one month, which is the whole feature.
- *Derive the period server-side from the latest actuals*: violates "user-selectable" and couples
  navigation to data shape; the user must be able to look at any closed month.

## R2 — Key the review store by `(current_period, flag_id)`

**Decision**: Extend the `ReviewStore` **port** so `get`, `upsert`, `list_all`, and `actions_for`
are scoped by `current_period`. `ReviewItem` gains a `current_period: int` field. The in-memory
double keys its dict by the tuple `(current_period, flag_id)`; actions are filtered by the pair. The
service seeds and reads items per period.

**Rationale**: Each as-of month is an independent review queue with its own lifecycle state (FR-005,
FR-006). Keying by the pair makes per-month isolation a property of the store, not of careful service
bookkeeping, and lets the same `flag_id` exist independently in two months. The port stays a clean
abstraction (Principle VI) because both adapters implement the same period-aware signature.

**Alternatives rejected**:
- *Namespace the period into the flag_id string*: hides a real dimension inside an identifier, breaks
  `actions_for(flag_id)`, and makes queries stringly-typed.
- *One store instance per period*: multiplies lifecycle/connection management for no gain; a single
  store with a composite key is simpler and matches the SQLite adapter naturally.

## R3 — SQLite schema change + recreate (migration note)

**Decision**: In `SqliteReviewStore`, add a `current_period` column to both `review_item` and
`review_action`, and make `review_item`'s primary key the composite `(current_period, flag_id)`
(the SQLite upsert `index_elements` becomes `["current_period", "flag_id"]`). Because the primary
key changes, an existing `build/review.db` from the old schema is **incompatible**. On startup the
adapter detects an incompatible existing `review_item` table (missing the `current_period` column)
and **recreates** the review tables (drop + `create_all`).

**Rationale**: The review DB is dev-only, git-ignored, and holds *mock* review state (Principle VIII)
— there is no production data to migrate, so a guarded recreate is the simplest correct path and also
clears the stale rows that contribute to the current desync (old flag_ids from before the data
rebuild). Detecting the missing column (via SQLAlchemy `inspect`) keeps it automatic rather than
relying on a human to delete the file.

**Alternatives rejected**:
- *Silent `create_all` only*: SQLAlchemy won't alter an existing table, so the old single-column PK
  would persist and writes would misbehave — exactly the lingering-state bug.
- *Hand-written ALTER/backfill migration*: overkill for a git-ignored mock DB; backfilling a period
  onto period-less rows is guesswork.
- *Require the developer to `rm build/review.db`*: works but is a footgun; auto-recreate on mismatch
  is friendlier and deterministic.

## R4 — Idempotent per-period seeding on first `/review`

**Decision**: `get_flags(current_period)` (called by `/review` and `/review/progress`) computes that
month's flagged variances and, for each flag without an existing item under that period, inserts a
`ReviewItem` in `DETECTED`. Seeding reads-then-inserts only missing items; it never updates or
deletes an existing item. Repeated calls for the same period are a no-op beyond the first.

**Rationale**: FR-007/FR-008 — first access seeds, later access must not duplicate or wipe work.
`_ensure_item` already implements get-or-create for a single flag; extending it with the period key
makes seeding idempotent by construction (an existing drafted/accepted item short-circuits).

**Alternatives rejected**:
- *Seed on a write/POST only*: a freshly opened month would show an empty queue until acted on —
  reintroduces the empty-queue symptom for any month other than the seeded one.
- *Wipe-and-reseed each request*: destroys in-progress drafts and decisions; violates FR-008.

## R5 — UI: as-of state, selectable months, and query-key threading

**Decision**:
- `Workspace.tsx` owns `const [currentPeriod, setCurrentPeriod] = useState(DEFAULT_PERIOD)` — UI
  state, exactly like `timeCut`. A new `AsOfSelector` (mirroring `TimeCutSelector`) sets it.
- `web/src/api/schema.ts` replaces the single `CURRENT_PERIOD = 6` constant with `DEFAULT_PERIOD = 6`
  (the latest month with actuals) and `AS_OF_PERIODS = [1,2,3,4,5,6]` (months with actuals, latest
  last). The selector renders `AS_OF_PERIODS`, default `DEFAULT_PERIOD`.
- `hooks/api.ts`: query keys become `["pnl", currentPeriod, timeCut]`, `["variances", currentPeriod]`,
  `["review", currentPeriod]`, `["progress", currentPeriod]`. Hooks take `currentPeriod`; the review
  and progress client calls pass `?current_period=`. Mutations carry `currentPeriod` and invalidate
  the review/progress keys **for that period**.
- The existing `time_cut` selector is unchanged and continues to slice relative to `currentPeriod`.

**Rationale**: Putting `current_period` in the query key is the idiomatic TanStack-Query way to make
"changing the month refetches everything for that month" automatic and cache-correct (each month's
data is cached independently, so returning to a month is instant and shows its own state — FR-009/
FR-011). It mirrors the existing `time_cut`-in-key pattern, so it's a minimal, familiar change.

**Alternatives rejected**:
- *Global/store-based period*: unnecessary; one Workspace-local `useState` suffices (no other
  consumer), consistent with the existing "lift only UI concerns" decision in Block 5.
- *A backend `/periods` endpoint to list selectable months*: cleaner long-term, but out of the user's
  stated scope ("a new selector plus a query-key change, not new screens"). The selectable set is a
  small UI constant for v0, documented as an assumption; a `/periods` endpoint is noted as the future
  upgrade when months become data-driven.

## R6 — No recompute in the API; Block 1 numbers untouched

**Decision**: Every figure and flag continues to come from `build_pnl` / `compute_variances` /
`flag_variances` via the engine; the API and store construct no number. The feature only selects the
`current_period` fed to the engine and routes review state by it. A determinism test asserts the flag
set for a fixed period is identical across `/variances`, `/review`, and `/review/progress`.

**Rationale**: Principle I is absolute. This change is pure selection/routing of already-deterministic
results, so it cannot perturb a figure. Keeping the assertion in the suite guards against any future
drift between the three endpoints.

**Alternatives rejected**: none — recomputing or caching figures in the API would violate Principle I.
