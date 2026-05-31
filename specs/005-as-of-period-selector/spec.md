# Feature Specification: As-of Period Selector (single source of truth for current_period)

**Feature Branch**: `005-as-of-period-selector`

**Created**: 2026-05-31

**Status**: Draft

**Input**: User description: "Feature + bug fix: make the 'as-of' period user-selectable so the user can navigate the P&L across months, and make current_period the single source of truth flowing through every layer. This also fixes the current bug where the review queue is empty — the grid and the review store are reading different current_periods."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review queue agrees with the grid for the chosen month (Priority: P1)

A controller opens the review workspace for the current as-of month (June, period 6). The P&L grid
shows the flagged lines for June, and the review queue on the right shows one card per flagged
variance for June. The two panes describe the *same* month and the *same* set of flags. Today,
the queue is empty even though the grid shows flagged lines, because the grid and the queue are
reading two different as-of months. This story makes them share one as-of month so they always
agree.

**Why this priority**: This is the headline bug. An empty review queue makes the entire workspace
unusable — there is nothing to investigate, answer, accept, or dismiss. Fixing the shared as-of
month is the minimum viable outcome and unblocks every other workflow.

**Independent Test**: Open the workspace at the default as-of month and confirm the review queue
is non-empty and lists exactly the flags the grid marks for that month. Verifiable end-to-end with
no other story implemented.

**Acceptance Scenarios**:

1. **Given** the default as-of month (period 6) with its embedded anomalies, **When** the controller
   opens the workspace, **Then** the review queue contains one card per flagged variance detected for
   that as-of month (across all time cuts and scenario pairs, per FR-004) and is not empty.
2. **Given** the workspace open at a given as-of month, **When** the controller compares the flagged
   lines in the grid with the cards in the queue, **Then** the flag set is identical — every marked
   grid line has a card and every card maps to a marked grid line.
3. **Given** any single as-of month, **When** the P&L, the variance list, the review queue, and the
   progress indicator are all requested for that month, **Then** they all report the same set of
   flags for that month (no pane uses a different as-of month than another).

---

### User Story 2 - Navigate the P&L across months (Priority: P2)

A controller wants to look back at an earlier month's P&L and its variances, then return to the
current month. They use an "As of" selector to choose the month the workspace is anchored to. The
grid, the variances, and the review queue all refresh to that month. The existing time-cut selector
(current month / YTD / full year / prior-month YTD) keeps working and now slices relative to the
chosen as-of month.

**Why this priority**: Cross-month navigation is the core new capability beyond the bug fix. It lets
a controller review history and prepare commentary for any closed month, not just the latest one.

**Independent Test**: Change the "As of" selector to an earlier month and confirm all three panes
refresh to that month's data; change the time-cut selector and confirm it slices relative to the
chosen as-of month, not a fixed one.

**Acceptance Scenarios**:

1. **Given** the workspace anchored to period 6, **When** the controller selects period 5 in the
   "As of" selector, **Then** the grid, the variance list, and the review queue all refresh to
   period 5's data.
2. **Given** an as-of month is selected, **When** the controller changes the time-cut selector,
   **Then** the slice (current month / YTD / full year / prior-month YTD) is computed relative to the
   selected as-of month.
3. **Given** the "As of" selector, **When** the controller opens it, **Then** it offers only months
   that have actuals and defaults to the latest such month.
4. **Given** the two selectors, **When** the controller changes either one, **Then** the other
   retains its value (the as-of month and the time cut are independent and coexist).

---

### User Story 3 - Per-month review work is preserved when switching months (Priority: P3)

A controller investigates and drafts commentary for several flagged variances in June, switches to
May to check something, then returns to June. All of June's review progress — investigations,
controller answers, drafts, and accepted/dismissed decisions — is exactly as they left it. Each
as-of month carries its own independent review queue and state.

**Why this priority**: Without per-month isolation, switching months would either lose work or bleed
one month's decisions into another. This makes month navigation safe and trustworthy, but it depends
on Stories 1 and 2 existing first.

**Independent Test**: Accept a draft and dismiss another in June, switch to May and act on May's
flags, return to June, and confirm June's accepted/dismissed/drafted states are unchanged and
distinct from May's.

**Acceptance Scenarios**:

1. **Given** review actions taken in period 6 (an accepted item, a dismissed item, a draft),
   **When** the controller switches to period 5 and back to period 6, **Then** period 6's items show
   their prior statuses and content unchanged.
2. **Given** a flag id that exists in more than one month, **When** the controller resolves it in one
   month, **Then** its status in the other month is unaffected (state is keyed per as-of month).
3. **Given** a month whose flags have never been opened, **When** the controller first requests its
   review queue, **Then** its flagged variances are seeded as "detected" without altering any other
   month's queue.

---

### Edge Cases

- **First visit to a month**: When a month's review queue is requested for the first time, the system
  detects that month's flagged variances and seeds them as "detected". Seeding is idempotent — a
  second request for the same month neither duplicates items nor resets existing statuses.
- **Re-seeding after work exists**: If some items for a month are already drafted/accepted/dismissed,
  a later request for that month's queue must not wipe or revert them; it may only add cards for
  flags not yet present (there should be none for an unchanged flag set).
- **Month with no flags**: A month whose variances breach no thresholds yields an empty-but-valid
  review queue (zero cards) and a progress indicator of 0 of 0 — not an error.
- **Period validation and empty months**: A request outside the fiscal range 1–12 is rejected
  (HTTP 422). A period within 1–12 that has no actuals returns an empty queue and progress 0 of 0 —
  it is never silently substituted with a different month. The "As of" selector only offers months
  with actuals, so non-actual periods are unreachable from the UI.
- **Flag-set drift guard**: For a fixed as-of month and unchanged inputs, the flag set is identical
  every time it is computed, so the grid, variances, queue, and progress never disagree due to
  recomputation.
- **Progress count scope**: The progress indicator counts resolved-of-total only within the selected
  as-of month, never across months.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST treat `current_period` (the "as-of" month, 1–12) as a single,
  explicit, user-selectable value that anchors every view in the workspace.
- **FR-002**: Every read view — the P&L grid, the variance list, the review queue, and the review
  progress indicator — MUST be computed for the *same* user-selected as-of month within a given
  workspace state. No view may fall back to a different default as-of month than another.
- **FR-003**: The system MUST accept the as-of month as an explicit parameter on every read view that
  depends on it, validated to the fiscal range 1–12. A period within range that has no actuals yields
  an empty-but-valid result (zero flags), never a fallback to a different month.
- **FR-004**: For a given as-of month, the set of flagged variances reported to the grid, to the
  variance list, and to the review queue MUST be identical.
- **FR-005**: The system MUST maintain a separate review queue and review state per as-of month, so
  that the status, answers, and drafted/accepted/dismissed content of one month's flags are
  independent of every other month's.
- **FR-006**: Review items MUST be identified by the combination of (as-of month, flag identifier),
  so the same flag identifier in two different months refers to two independent review items.
- **FR-007**: On the first request for an as-of month's review queue whose flags are not yet present,
  the system MUST detect that month's flagged variances and seed them in the "detected" state.
- **FR-008**: Seeding MUST be idempotent — repeated requests for the same as-of month MUST NOT create
  duplicate review items and MUST NOT overwrite, revert, or wipe existing review state for that month.
- **FR-009**: Switching to a different as-of month and returning MUST preserve the original month's
  review state exactly (every status and all associated content unchanged).
- **FR-010**: The workspace MUST present an "As of" month selector offering only months that have
  actuals, defaulting to the latest such month (period 6).
- **FR-011**: Selecting an as-of month MUST refresh the grid, the variance list, and the review queue
  to that month together, so the panes never display a mix of months.
- **FR-012**: The existing time-cut selector (prior-month YTD / current month / YTD / full year) MUST
  continue to operate and MUST slice relative to the selected as-of month; the as-of selector and the
  time-cut selector MUST coexist as independent controls.
- **FR-013**: The review progress indicator MUST report resolved-of-total counted only within the
  selected as-of month.
- **FR-014**: The feature MUST NOT change any financial figure produced by the deterministic engine
  (Block 1 numbers are untouched); it only selects *which* month's already-deterministic figures and
  flags are shown and reviewed.

### Key Entities *(include if feature involves data)*

- **As-of month (`current_period`)**: The fiscal month the workspace is anchored to (1–12).
  Distinct from the time cut. It is the single source of truth that selects which month's P&L,
  variances, and review queue are shown. Valid values are the months that have actuals.
- **Review item**: A single flagged variance under review, identified by (as-of month, flag
  identifier), carrying its lifecycle status (detected / investigating / awaiting_controller /
  drafted / accepted / dismissed / failed) and associated content (question, answer, draft).
- **Review queue (per month)**: The collection of review items for one as-of month, seeded from that
  month's flagged variances on first access and persisted independently of other months.
- **Time cut**: The relative slice (prior-month YTD / current month / YTD / full year) applied on top
  of the selected as-of month. Unchanged by this feature except that it now slices relative to the
  user-selected as-of month.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For the default as-of month with its embedded anomalies, the review queue is non-empty
  and contains exactly one card per flagged variance for that month (0 missing, 0 extra).
- **SC-002**: For any single as-of month, the flag set reported to the grid, the variance list, and
  the review queue is identical in 100% of cases (no pane-to-pane disagreement).
- **SC-003**: After taking review actions in one month, switching to another month, and returning,
  100% of the first month's review items retain their prior status and content.
- **SC-004**: Requesting the same as-of month's review queue any number of times produces the same
  number of review items and the same statuses — repeated access never duplicates or resets state.
- **SC-005**: A controller can switch the as-of month and see all three panes reflect the newly
  selected month, with the time-cut selector still slicing relative to that month.
- **SC-006**: The deterministic engine's figures are unchanged — every existing Block 1 reconciliation
  and figure test continues to pass.

## Assumptions

- The available as-of months are the months that have current-year actuals (periods 1–6 in the
  current mock dataset); the selector defaults to the latest, period 6.
- The as-of month is an explicit input at every layer and is never derived from the wall clock,
  consistent with the project's determinism principle.
- This feature changes *selection and routing* of already-computed figures and flags; it does not
  introduce any new financial computation and does not alter the engine, the flagging thresholds, or
  the agent's grounding flow.
- Per-month review state lives in the existing review store; this feature extends its key to include
  the as-of month and reuses the existing lifecycle and seeding behavior.
- The OpenRouter key and all model access remain backend-only and out of scope for this feature.
- Mock data only; no real client data is introduced.
