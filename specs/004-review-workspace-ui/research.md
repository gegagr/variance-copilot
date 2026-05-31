# Phase 0 Research: Review Workspace UI (Block 5)

The three clarify-session decisions (API-served display strings; one card per flag with line→cards
grouping; per-card + "investigate all" trigger) are encoded in the spec. This research resolves
*how* to realise them with React/Vite/TanStack Query while keeping the UI free of figure arithmetic.

---

## R1. The display-string dependency (the constitutional anchor) — Block 4 addition

**Decision**: Add a deterministic Python formatter and have Block 4 serve a **display string per
figure** alongside the raw value. Concretely:
- `engine/format.py` (pure, tested): `money(Decimal) -> "€1,234.00"`, `percent(Decimal) ->
  "16.7%"`, `points(Decimal) -> "+1.8 pp"` — fixed precision, deterministic, no locale surprises.
- Block 4 adds thin **view DTOs** that attach display strings without touching Block 1/3 raw
  contracts (which keep exact Decimals for provenance): a `PnlCellView { value, display, is_margin }`
  projection for the P&L, and figure display fields on the served variance/commentary (e.g.
  `current_display`, `comparator_display`, `abs_display`, `pct_display`, `pp_display`).
- The UI renders ONLY the `*_display` strings; raw values remain available for keys/sorting but are
  never reformatted by the UI.

**Rationale**: Determinism First at the presentation layer — "a Python function created every
number AND its representation." Formatting in deterministic Python (not JS) means the UI literally
cannot violate the rule; the guard test then just asserts the UI prints the served string.

**Alternatives considered**: UI formats raw ratios with JS (`×100`, `toLocaleString`) — rejected,
that is arithmetic/derivation in the presentation layer. Showing raw ratios like "0.1667" —
rejected as unfinished for a finance UI.

## R2. Typed API client from OpenAPI

**Decision**: Generate `web/src/api/types.ts` from the FastAPI `/openapi.json` (e.g.
`openapi-typescript`) and wrap `fetch` in a thin typed `client.ts` (the only network access). Types
are regenerated from the running backend, never hand-maintained.

**Rationale**: The OpenAPI schema is the Block 4 contract (FR-018); generation keeps the frontend
in lockstep and surfaces breaking changes at compile time.

**Alternatives considered**: Hand-written types (drift); a heavy generated SDK (more than needed).

## R3. TanStack Query owns server state; mutations invalidate

**Decision**: One query hook per resource — `usePnl(timeCut)`, `useVariances()`, `useReview()`
(items + progress + accepted) — and a `useReviewActions()` set of mutations (investigate, answer,
accept, edit, dismiss). Each mutation, on success, **invalidates** the review/progress queries so
the UI refetches and mirrors the API's review state (FR-011/FR-012/FR-014). Cards read from query
data; no card holds its own lifecycle copy.

**Rationale**: Mutations-invalidate-then-refetch makes "card status always matches the API" the
default behavior, not bespoke wiring. Per-query loading/error states give the investigating and
error treatments for free.

**Alternatives considered**: Optimistic status updates (risk of showing a state the API didn't
confirm — rejected for the lifecycle; the only "optimistic" affordance is the pending/investigating
spinner, which is the query's own pending state).

## R4. Anchoring index (one card per flag; group by line)

**Decision**: `lib/anchor.ts` builds a `line → flag_ids[]` index from the variance list and the
inverse `flag_id → line`. `Workspace.tsx` holds `selectedFlagId` (UI state). Selecting a grid line
sets selection to that line's cards (scrolls the queue to and emphasizes the group); selecting a
card sets `selectedFlagId` and the grid highlights that card's line. A line may map to several
cards (across scenario pairs / time cuts).

**Rationale**: The clarified model — granular cards, grouped on selection. A pure index keeps
anchoring testable and decoupled from rendering.

**Alternatives considered**: One card per line (loses per-variance status/actions — rejected).

## R5. Investigating (pending) + error states

**Decision**: The investigate mutation's `isPending` drives the card's investigating state; the
card disables conflicting actions while pending. `isError` (or an API failure / Block 3 fail-safe
returning `detected`) renders an error/failed treatment on that card only; the rest of the
workspace is unaffected because state is per-query/per-card. An error boundary wraps the workspace
as a last resort.

**Rationale**: FR-015/FR-016, SC-006/SC-007. Per-mutation state localises failure to one card.

**Alternatives considered**: A global blocking spinner (poor UX, violates "other cards remain
usable").

## R6. The no-arithmetic guard

**Decision**: Two layers. (a) A unit/lint-style test (`noArithmetic.test.ts`) scans
`src/components` and `src/lib/format.ts` and fails on figure arithmetic — `parseFloat`/`Number(`
applied to served figure fields, or `* / + -` on display values. (b) A render test asserts a grid
cell's text === the API's served `display` string character-for-character (SC-001).

**Rationale**: Makes "the UI computes no figure" a CI-enforced invariant, the presentation-layer
analogue of Block 3's guard and Block 4's pass-through test.

**Alternatives considered**: Trusting code review (not enforceable — rejected).

## R7. Visual direction (finance-SaaS, not terminal)

**Decision**: Tailwind theme tokens — light surfaces, one indigo accent (`accent`), semantic colors
(`favorable`/`unfavorable` for variance direction; per-status card colors), Inter font with
`font-variant-numeric: tabular-nums` on all grid numbers. No monospace anywhere for content; no
dark console theme. shadcn/ui primitives (Radix) for cards, inputs, buttons, selects.

**Rationale**: FR-017/FR-018, SC-009. Tokenised theme makes the visual checks testable and
consistent.

**Alternatives considered**: A component kit with a dark default (fights the brief — rejected).

## R8. Offline deterministic tests with MSW

**Decision**: MSW (`tests/msw/handlers.ts`) serves deterministic Block 4 fixtures (a P&L, a flag
list, scripted investigation responses, and review-action results). Component tests render cards in
each status; interaction tests drive answer/accept/edit-then-accept/dismiss and assert the UI shows
the returned status; an anchoring test covers line↔card selection. No real backend, no network.

**Rationale**: The user's testing list; deterministic and CI-friendly. MSW intercepts at the
network layer so the typed client is exercised as in production.

**Alternatives considered**: Stubbing the client module (skips the fetch/typing path — weaker).

## R9. Vite dev proxy + key safety

**Decision**: `vite.config.ts` proxies `/api` to the local FastAPI backend in dev; the client uses
a configurable base URL (`/api` by default). The OpenRouter key lives only on the backend; the
frontend never references it and never calls the model.

**Rationale**: DEV/INTEGRATION + VIII (no secrets in the UI).

**Alternatives considered**: CORS-only direct calls (works too; proxy keeps origins simple in dev).

## R10. "Investigate all" sequential runner

**Decision**: A workspace action iterates the not-yet-investigated cards and runs the investigate
mutation **sequentially** (await each before the next), reflecting each card's resulting status as
it lands. It is controller-initiated; nothing auto-runs on load.

**Rationale**: FR-011a; sequential matches Block 4's synchronous per-variance endpoint and avoids a
burst of concurrent long calls.

**Alternatives considered**: Parallel fan-out (hammers the backend/model; harder to surface
per-card progress) — rejected for v0. Auto-run on load — rejected by the clarification.

---

## Resolved unknowns summary

| Topic | Resolution |
|-------|-----------|
| Figure formatting | Block 4 serves Python-formatted display strings; UI renders verbatim (R1) |
| Types | Generated from `/openapi.json`; thin typed fetch client (R2) |
| Server state | TanStack Query hooks; mutations invalidate → refetch (R3) |
| Anchoring | `line ↔ cards` index; selected-flag UI state; group on line select (R4) |
| Async/errors | Per-mutation pending/error → per-card investigating/error treatment (R5) |
| No-arithmetic | Scan test + rendered-text===display-string test (R6) |
| Visual | Tailwind tokens: indigo accent, semantic colors, Inter tabular figures, no monospace (R7) |
| Tests | Vitest + RTL + MSW, offline/deterministic (R8) |
| Dev/secrets | Vite proxy `/api`; OpenRouter key backend-only (R9) |
| Investigate all | Controller-initiated sequential runner; no auto-run (R10) |
