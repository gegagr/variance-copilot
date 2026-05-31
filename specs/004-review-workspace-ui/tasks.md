---

description: "Task list for Review Workspace UI (Block 5)"
---

# Tasks: Review Workspace UI (Block 5)

**Input**: Design documents from `specs/004-review-workspace-ui/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: INCLUDED — the spec and the user's rules mandate test-first for the VarianceCard status
variants and the mutation flows. All tests run offline/deterministically via Vitest + React Testing
Library + MSW (no live API, no LLM key).

**Organization**: Tasks are grouped by user story (P1–P5 from spec.md). The user's dependency order
(scaffold → types+client → hooks → MSW → components test-first → workspace/anchoring → mutations →
interaction tests → dev proxy) is honored within and across the phases below.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US5 (user-story phases only)
- Frontend paths are under `web/`; the one backend dependency is under `engine/` + `api/`.

## Path Conventions

A standalone `web/` SPA (React + TS + Vite) consuming Block 4 only. The UI **computes no financial
figure** — it renders the API's display strings verbatim. Types are generated from `/openapi.json`;
all network access goes through one typed client. One small backend addition (display strings) is
required and sequenced first.

---

## Phase 1: Setup (Scaffold + the backend display-string dependency)

**Purpose**: A running web/ toolchain and the Block 4 display-string addition the UI depends on.

### Backend dependency (deterministic Python formatting — sequence first)

- [x] T001 Implement `engine/format.py`: pure `money(Decimal)->"€1,234.00"`, `percent(Decimal)->"16.7%"`, `points(Decimal)->"+1.8 pp"`, `not_meaningful()->"n/m"` (fixed precision; ×100 for percent happens HERE) per contracts/display-string.md
- [x] T002 [P] Block 1/format test: exact strings for representative values (e.g. `money("78600.00")=="€78,600.00"`, `percent("0.166667")=="16.7%"`, `points("0.017857")=="+1.8 pp"`) in `tests/test_format.py`
- [x] T003 Add `PnlCellView` and `FlaggedVarianceView` (raw fields + `*_display` strings) to `api/schemas.py` and serve them from NEW endpoints `GET /pnl/view` and `GET /variances/view`. Leave the existing `GET /pnl` and `GET /variances` byte-pure (do NOT change their shape) so Block 4's verbatim pass-through tests (`tests/test_api_pnl.py`) stay green. Add a test that the `/view` endpoints' `*_display` equal `format.*` of the raw values in `tests/test_api_display_strings.py` (depends on T001)

### Frontend scaffold

- [x] T004 Scaffold the Vite + React + TypeScript app in `web/` (`package.json`, `index.html`, `tsconfig.json`, `src/main.tsx`, `src/App.tsx`); app runs with `pnpm dev`
- [x] T005 [P] Configure Tailwind CSS + theme tokens (light surfaces, single indigo `accent`, semantic `favorable`/`unfavorable` + per-status colors, Inter font, `tabular-nums` utility) in `web/tailwind.config.ts` + `web/src/styles/index.css`
- [x] T006 [P] Initialize shadcn/ui (Radix primitives) into `web/src/components/ui/` (card, button, textarea, select, badge, progress)
- [x] T007 [P] Configure Vitest + React Testing Library + jsdom in `web/vite.config.ts` and `web/tests/setup.ts`

---

## Phase 2: Foundational (Types, client, hooks, MSW) — Blocking Prerequisites

**Purpose**: The typed API seam, server-state hooks, and the offline MSW harness every story needs.

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

- [x] T008 Generate `web/src/api/types.ts` from the backend `/openapi.json` (e.g. `openapi-typescript`); add a `pnpm gen:api` script. Committed but regenerable, never hand-edited (depends on T003)
- [x] T009 Implement the thin typed fetch client (the ONLY network access; base URL `/api`) in `web/src/api/client.ts` (depends on T008)
- [x] T010 [P] Implement `web/src/lib/format.ts` — DISPLAY-ONLY helpers (e.g. apply color class by direction); it MUST NOT transform a served figure string (no parse/×100/round)
- [x] T011 [P] Implement `web/src/lib/anchor.ts` — pure `line→flagIds[]` and `flagId→line` index builders (one card per flag; a line may map to many)
- [x] T012 Implement TanStack Query hooks in `web/src/hooks/`: `usePnl(timeCut)` (→ `GET /pnl/view`), `useVariances()` (→ `GET /variances/view`), `useReview()` (items + progress), `useAccepted()`, and `useReviewActions()` (investigate/answer/accept/edit/dismiss mutations that invalidate review+progress on success) (depends on T009)
- [x] T013 Set up MSW with deterministic Block 4 fixtures (a P&L w/ display strings, a flag list, scripted investigation→question/draft, review-action results) in `web/tests/msw/handlers.ts` + server wiring in `web/tests/setup.ts` (depends on T008)
- [x] T014 [P] No-arithmetic guard test: scans `web/src/components` + `web/src/lib/format.ts` and fails on figure arithmetic (`parseFloat`/`Number(`/`* / + -` on served figures) in `web/tests/noArithmetic.test.ts`

**Checkpoint**: Types, client, hooks, MSW, and the no-arithmetic guard exist — components can begin.

---

## Phase 3: User Story 1 - Workspace render (P&L grid, queue, progress) (Priority: P1) 🎯 MVP

**Goal**: Render the P&L grid (line/subtotal/margin rows with flagged markers), the variance queue
(one card per flag), and the progress bar — all from API data, figures verbatim.

**Independent Test**: With MSW fixtures, the grid shows served lines/columns with subtotals and
margins, flagged lines are marked, one card per flag appears, progress matches the API, and every
cell's text equals the served `display` string.

### Tests for User Story 1 ⚠️ (write first, must fail)

- [x] T015 [P] [US1] PnlGrid render test: line/subtotal/margin row variants render; flagged lines carry a marker; each cell's text === the served `display` string (SC-001) in `web/tests/pnlGrid.test.tsx`

### Implementation for User Story 1

- [x] T016 [P] [US1] Implement `ProgressBar` (resolved/total from `useReview`) in `web/src/components/ProgressBar.tsx`
- [x] T017 [US1] Implement `PnlGrid` with row variants (line, subtotal, margin sub-row) rendering served `display` strings, tabular figures, direction colors, and a flagged-line marker, in `web/src/components/PnlGrid.tsx` (depends on T012)
- [x] T018 [US1] Implement `VarianceReviewPanel` (the queue: one `VarianceCard` per flag) in `web/src/components/VarianceReviewPanel.tsx` (depends on T012; card from US2)

**Checkpoint**: The workspace renders P&L + queue + progress from API data — MVP read-through.

---

## Phase 4: User Story 2 - The variance card per lifecycle status (Priority: P2)

**Goal**: A `VarianceCard` with a distinct variant per status (detected, investigating,
awaiting-controller, drafted, accepted, dismissed), showing the right content and controls, status
always mirroring the API.

**Independent Test**: Render the card in each status (MSW/fixtures); assert the correct controls and
content appear per the ui-states matrix and that figures render from display strings.

### Tests for User Story 2 ⚠️ (write first, must fail)

- [x] T019 [P] [US2] VarianceCard status tests: for each of the 6 statuses, the correct controls/content appear (detected→Investigate; investigating→disabled spinner; awaiting→question+hypothesis+answer input+Submit; drafted→Accept/Edit/Dismiss; accepted→settled+Edit/Dismiss; dismissed→settled) per contracts/ui-states.md, in `web/tests/VarianceCard.status.test.tsx`

### Implementation for User Story 2

- [x] T020 [US2] Implement `VarianceCard` with a variant per lifecycle status (content + gated controls + per-status visual treatment), rendering variance figures from `*_display`, in `web/src/components/VarianceCard.tsx` (depends on T012)
- [x] T021 [US2] Implement the per-card investigating (mutation `isPending`) and error/fail-safe treatments without crossing into other cards, in `web/src/components/VarianceCard.tsx` (depends on T020)

**Checkpoint**: Cards reflect every lifecycle status with correct controls, independently testable.

---

## Phase 5: User Story 3 - Workspace shell + bidirectional anchoring + time cut (Priority: P3)

**Goal**: The two-pane Workspace that owns `selectedFlagId` + `timeCut`, wires anchoring
(line↔cards), and switches the grid cut.

**Independent Test**: Selecting a marked grid line emphasizes/scrolls to its card group; selecting a
card highlights its line; changing the time cut switches the grid's columns from served data.

### Tests for User Story 3 ⚠️ (write first, must fail)

- [x] T022 [P] [US3] Anchoring + time-cut tests: clicking a grid line focuses its card(s); clicking a card highlights its line; changing the time cut shows that cut's columns (no recomputation) in `web/tests/anchoring.test.tsx`

### Implementation for User Story 3

- [x] T023 [US3] Implement `TimeCutSelector` (prior-month YTD / current month / YTD / full year) in `web/src/components/TimeCutSelector.tsx`
- [x] T024 [US3] Implement `Workspace` shell (two panes) owning `selectedFlagId` + `timeCut`; wire bidirectional anchoring via `lib/anchor.ts`; pass selection/cut to `PnlGrid` and `VarianceReviewPanel` in `web/src/components/Workspace.tsx` and `web/src/App.tsx` (depends on T017, T018, T020, T023)

**Checkpoint**: A composed workspace with working anchoring and time-cut switching.

---

## Phase 6: User Story 4 - Investigate + answer flow (Priority: P4)

**Goal**: Trigger investigations (per card + "investigate all" sequential), watch the investigating
state, then answer a question to get a draft — each via the API, the card reflecting the response.

**Independent Test**: (MSW) trigger investigate → card shows investigating then question/draft;
submit an answer on an awaiting card → it becomes drafted; "investigate all" runs pending cards
sequentially; a failed investigation shows an error without crashing.

### Tests for User Story 4 ⚠️ (write first, must fail)

- [x] T025 [P] [US4] Investigate + answer interaction tests (MSW): investigate → investigating → question/draft; answer → drafted with returned commentary; empty answer blocked client-side; failed investigation → error treatment, workspace stays usable; "investigate all" runs sequentially, in `web/tests/reviewFlow.test.tsx`

### Implementation for User Story 4

- [x] T026 [US4] Wire the investigate + answer mutations into `VarianceCard` (Submit gated on non-empty answer) so each calls the API and the card shows the returned status in `web/src/components/VarianceCard.tsx` (depends on T012, T020)
- [x] T027 [US4] Implement the "investigate all" sequential runner (awaits each pending card before the next) in `web/src/components/Workspace.tsx` (depends on T024, T026)

**Checkpoint**: Investigation + answer flows work offline against MSW, reflecting API state.

---

## Phase 7: User Story 5 - Accept / edit-then-accept / dismiss (Priority: P5)

**Goal**: Act on a draft — accept, edit then accept, or dismiss — each via the API; the card and
progress reflect the returned status; settled cards de-emphasize.

**Independent Test**: (MSW) accept a drafted card → accepted/settled, progress +1; edit then accept →
accepted text reflects the edit; dismiss → dismissed/settled, progress +1; status always matches the
API response.

### Tests for User Story 5 ⚠️ (write first, must fail)

- [x] T028 [P] [US5] Accept/edit/dismiss interaction tests (MSW): accept→accepted (progress updates); edit-then-accept→accepted text equals the edit (SC-005); dismiss→dismissed and excluded; status mirrors the API after each; AND a rejected action (API returns 409) reconciles the card to the API's returned status (no stale optimistic state) and surfaces a non-blocking notice (FR-012), in `web/tests/reviewFlow.test.tsx`

### Implementation for User Story 5

- [x] T029 [US5] Wire accept / dismiss mutations into `VarianceCard`; settle + de-emphasize accepted/dismissed; progress refetches via invalidation in `web/src/components/VarianceCard.tsx` (depends on T012, T020)
- [x] T030 [US5] Implement the inline edit affordance (seed editor with current commentary; Save+Accept = edit then accept; edit alone stays drafted) in `web/src/components/VarianceCard.tsx` (depends on T029)

**Checkpoint**: Full Human-in-the-Loop review works end to end against MSW.

---

## Phase 8: Dev integration & polish (last)

- [x] T031 Configure the Vite dev proxy `/api` → local FastAPI backend in `web/vite.config.ts`; document `pnpm gen:api` + `pnpm dev` (key stays backend-only)
- [x] T032 [P] Visual-direction check: a test/lint assertion that content uses no monospace and grid numbers use `tabular-nums`, and a manual checklist note (indigo accent, semantic colors) in `web/tests/visual.test.tsx`
- [x] T033 [P] Empty/error states: empty queue state and a workspace-level error boundary so a failed query never blanks the screen, in `web/src/components/Workspace.tsx`
- [x] T034 [P] Update project `README.md` with the `web/` run/test instructions and an SC-traceability note (SC-001…SC-010 → tests)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: backend display strings (T001→T003) sequence FIRST (the UI depends on them);
  frontend scaffold (T004–T007) in parallel with the backend work.
- **Foundational (Phase 2)**: depends on Setup. Order: types (T008) → client (T009) → hooks (T012);
  MSW (T013) after types; `lib/*` (T010/T011) and the guard (T014) in parallel.
- **User Stories**: US1 (render) → US2 (card) → US3 (workspace/anchoring) → US4 (investigate/answer)
  → US5 (accept/edit/dismiss). US1's queue uses US2's card, so US2 lands alongside/just after US1.
- **Polish (Phase 8)**: last; the dev proxy (T031) is needed only for a *live* run, not the tests.

### Critical-path note (honoring the user's sequencing)

```
format.py(T001)→display DTOs(T003) → scaffold(T004) → types(T008)→client(T009)→hooks(T012)
   → MSW(T013) → VarianceCard test-first(T019)→impl(T020) + PnlGrid(T017)/selectors(T016,T023)
       → Workspace + anchoring(T024) → investigate/answer(T026,T027) → accept/edit/dismiss(T029,T030)
           → interaction tests(T025,T028) → dev proxy(T031)
```

### Parallel Opportunities

- Setup: backend (T001–T003) ∥ frontend scaffold (T004–T007); within scaffold T005/T006/T007 ∥.
- Foundational: T010, T011, T014 ∥ after types; T013 after T008.
- Per-story test tasks (T015, T019, T022, T025, T028) ∥ (separate files), each before its impl.
- Tasks touching `web/src/components/VarianceCard.tsx` (T020, T021, T026, T029, T030) share a file →
  sequence them; cards in different files (PnlGrid, ProgressBar, TimeCutSelector) are ∥.
- Polish: T032, T033, T034 ∥.

---

## Parallel Example: Foundational

```bash
# After T008/T009 (types + client):
Task: "TanStack Query hooks in web/src/hooks/"                 # T012
Task: "Display-only helpers in web/src/lib/format.ts"          # T010
Task: "Anchor index in web/src/lib/anchor.ts"                  # T011
Task: "No-arithmetic guard test in web/tests/noArithmetic.test.ts"  # T014
```

## Parallel Example: card test-first

```bash
Task: "VarianceCard status tests in web/tests/VarianceCard.status.test.tsx"  # T019 (must fail first)
Task: "PnlGrid render test in web/tests/pnlGrid.test.tsx"                     # T015
```

---

## Implementation Strategy

### MVP First (Setup + Foundational + US1 + the card)

1. Phase 1 (incl. the backend display strings) → 2. Phase 2 (types/client/hooks/MSW/guard) →
3. US2 card (so the queue has cards) → 4. US1 render. **STOP and VALIDATE**: the workspace renders
the P&L grid, queue, and progress entirely from API data, with figures shown verbatim from display
strings — the constitutional guarantee proven by the no-arithmetic guard + the cell-text===display
test.

### Incremental Delivery

1. Setup + Foundational → typed, offline-testable shell.
2. US1 + US2 → render + cards (MVP).
3. US3 → workspace shell + anchoring + time cut.
4. US4 → investigate + answer.
5. US5 → accept / edit-then-accept / dismiss.
6. Polish → dev proxy, visual check, empty/error states.

Each increment is independently testable (MSW) and adds value without breaking the prior.

---

## Notes

- `[P]` = different files, no incomplete dependencies. The five tasks on `VarianceCard.tsx`
  (T020/T021/T026/T029/T030) share a file and are intentionally NOT `[P]` among themselves.
- Tests precede implementation for the card status variants (T019) and the mutation flows (T025,
  T028), per the user's rules. All tests run offline via MSW — no live API, no LLM key.
- Constitution guards: T014 (no figure arithmetic in the UI) + T015 (cell text === served display);
  the OpenRouter key never appears in `web/` (no task adds an LLM call from the frontend); card
  status always mirrors the API (mutations invalidate → refetch).
- Backend untouched EXCEPT the display-string addition (T001–T003), which adds NEW `/pnl/view` and
  `/variances/view` endpoints and leaves the existing byte-pure `/pnl` `/variances` (and their
  pass-through tests) unchanged — keeping all number formatting in deterministic Python with zero
  regression to Block 4.
- The canonical API status value is `awaiting_controller` (underscore); the hyphenated
  "awaiting-controller" in spec prose is display only. The UI consumes the underscore enum.
- Commit after each task or logical group.
