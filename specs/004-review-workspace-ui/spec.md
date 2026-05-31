# Feature Specification: Review Workspace UI (Block 5)

**Feature Branch**: `004-review-workspace-ui`

**Created**: 2026-05-31

**Status**: Draft

**Input**: User description: "Specify Block 5: the web UI — the controller's review workspace. The interface a controller uses to review flagged variances, answer the agent's questions, and accept, edit, or dismiss the drafted commentary. It consumes the Block 4 API and renders what the API serves. Per the constitution at the presentation layer, it displays figures but never computes them."

## Overview

Block 5 is the controller's **review workspace** — the screen where a finance controller reviews
flagged P&L variances, answers the agent's grounded questions, and accepts, edits, or dismisses
the drafted commentary. It is a presentation layer over the Block 4 API: it renders exactly what
the API serves and routes every action back through the API. Per the constitution at the
presentation layer, it **displays figures but never computes them** — it shows the numbers the
API returns and performs no arithmetic on any financial figure.

The workspace is two anchored panes: a P&L grid on the left and a variance review queue on the
right, kept in sync bidirectionally. A time-cut selector switches which cut the grid shows, and a
progress indicator tracks how many variances are resolved. Each variance is a card that reflects
the API's review lifecycle — detected, investigating, awaiting-controller, drafted, accepted, or
dismissed — with distinct visual treatment per status. v0 covers the review workspace screen only:
no config editing, no data-source/import screens, no report export view.

## Clarifications

### Session 2026-05-31

- Q: How should percentages be displayed, given the UI must not compute figures but Block 4 serves raw ratios? → A: Extend Block 4 to serve a deterministic, display-ready formatted string per figure (e.g. "16.7%", "€78,600.00") produced by Python; the UI renders those verbatim and performs zero arithmetic. (Records a small Block 4 / API-contract dependency.)
- Q: A reporting line can carry several flagged variances — how do grid lines and cards anchor? → A: One card per flagged variance (a line may have several). Selecting a marked line focuses/scrolls to and groups the queue to that line's cards; selecting a card highlights its line.
- Q: How are investigations triggered in v0? → A: Per-card manual trigger on demand, plus a single "investigate all" convenience that runs them sequentially. No auto-run on load.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the P&L grid, the review queue, and progress (Priority: P1)

The controller opens the workspace and sees, on the left, the P&L grid for the selected period —
reporting lines with their scenario and variance columns, subtotals, and margin sub-rows, in the
layout the API serves — with flagged lines visibly marked; on the right, the variance review queue
with one card per flagged variance; and a progress indicator showing how many variances are
resolved of the total. Every figure shown is exactly what the API returned.

**Why this priority**: Without rendering the P&L, the queue, and progress from API data, there is
no workspace. This is the foundational, independently valuable read-through view.

**Independent Test**: Load the workspace against the API; confirm the grid shows the served P&L
lines/columns with subtotals and margins, flagged lines are marked, one card appears per flagged
variance, the progress indicator matches the API's resolved/total, and every displayed figure
equals the API's served value (no recomputation).

**Acceptance Scenarios**:

1. **Given** the API serves a P&L and flagged variances, **When** the workspace loads, **Then**
   the grid renders the reporting lines with scenario and variance columns, subtotals, and margin
   sub-rows in the served layout order, and lines with flagged variances carry a visible marker.
2. **Given** the served flagged-variance list, **When** the queue renders, **Then** there is
   exactly one card per flagged variance, each showing its variance figures as served.
3. **Given** the API's progress data, **When** the progress indicator renders, **Then** it shows
   the resolved count out of the total, matching the API.
4. **Given** any figure in the grid or a card, **When** it is compared to the API response,
   **Then** the displayed value equals the served value — the UI applies only non-arithmetic
   formatting (digit grouping, currency glyph, sign, color) and never re-derives a number.

---

### User Story 2 - Anchored navigation and time-cut switching (Priority: P2)

The controller can move between the grid and the queue: selecting a marked line focuses its card,
and selecting a card highlights its line in the grid. A time-cut selector (prior-month YTD, current
month, YTD, full year) switches which cut the grid shows.

**Why this priority**: Anchoring is what makes the two panes a single workspace rather than two
lists; the time-cut selector is how the controller frames the numbers. Both depend on US1's render.

**Independent Test**: Click a marked grid line → its card is focused/scrolled into view; click a
card → its grid line is highlighted; change the time-cut → the grid shows the corresponding cut's
columns, all from already-served data without recomputation.

**Acceptance Scenarios**:

1. **Given** a marked line with one or more cards, **When** the controller selects the line,
   **Then** the queue focuses/scrolls to and groups that line's card(s) and they are visually
   emphasized.
2. **Given** a card, **When** the controller selects it, **Then** the corresponding grid line is
   highlighted.
3. **Given** the time-cut selector, **When** the controller picks a different cut, **Then** the
   grid displays that cut's scenario/variance columns from the served P&L, with no figure
   recomputed by the UI.

---

### User Story 3 - Trigger an investigation and watch it progress (Priority: P3)

The controller triggers an AI investigation for a flagged variance. While the live call runs, the
card shows an investigating state; when it completes, the card becomes either a question
(awaiting-controller) or a draft. A failed investigation is surfaced on the card without crashing
the view.

**Why this priority**: Investigation is the agent's core contribution; the controller drives it per
variance and must see progress and failures. Depends on US1's cards.

**Independent Test**: Trigger an investigation on a detected card; confirm it shows the
investigating state during the call and then transitions to awaiting-controller or drafted per the
API; trigger "investigate all" and confirm pending cards are investigated sequentially; simulate a
failed investigation and confirm the card shows an error state and the rest of the workspace
remains usable.

**Acceptance Scenarios**:

1. **Given** a card in detected, **When** the controller triggers its investigation, **Then** the
   card shows an investigating (in-progress) state while the call is in flight.
2. **Given** the investigation completes, **When** the API returns the record, **Then** the card
   updates to awaiting-controller (showing the question + hypothesis) or drafted (showing the
   proposed commentary), matching the API status.
3. **Given** an investigation that fails, **When** the error is returned, **Then** the card shows
   an error/failed state, no commentary is shown, and the rest of the workspace keeps working.
4. **Given** several detected cards, **When** the controller triggers "investigate all", **Then**
   the pending investigations run sequentially and each card updates to its resulting status.

---

### User Story 4 - Answer the agent's question (Priority: P4)

For a card awaiting the controller, the controller reads the agent's grounded question and its
hypothesis, types an answer, and submits it. The card returns a draft built from the answer.

**Why this priority**: Closing the question loop is how an open variance becomes a reviewable draft.
Depends on US3 having produced a question.

**Independent Test**: On an awaiting-controller card, read the question + hypothesis, enter an
answer, submit; confirm the API is called and the card updates to drafted with the returned
commentary.

**Acceptance Scenarios**:

1. **Given** a card in awaiting-controller, **When** it renders, **Then** it shows the agent's
   question and stated hypothesis and an input for the controller's answer with a submit action.
2. **Given** a typed answer, **When** the controller submits, **Then** the API is called with the
   answer and the card updates to drafted, showing the returned commentary.
3. **Given** an empty answer, **When** submit is attempted, **Then** the UI prevents submission or
   surfaces a clear prompt, without calling the API with nothing.

---

### User Story 5 - Accept, edit, or dismiss a draft (Priority: P5)

For a drafted card, the controller accepts the commentary, edits it then accepts, or dismisses the
variance. Each action calls the API and the card reflects the resulting status; accepted and
dismissed cards settle into a de-emphasized state with the accepted text visible, and progress
updates.

**Why this priority**: This is the controller's decision point — the Human-in-the-Loop core — and
what advances review to done. Depends on US3/US4 producing a draft.

**Independent Test**: On a drafted card, exercise accept, edit-then-accept, and dismiss; confirm
each calls the API, the card's status updates to match, an edited draft's accepted text reflects
the edit, dismissed/accepted cards are de-emphasized, and progress increments.

**Acceptance Scenarios**:

1. **Given** a drafted card, **When** the controller accepts, **Then** the API is called and the
   card moves to accepted (settled, de-emphasized) with the accepted text visible; progress updates.
2. **Given** a drafted card, **When** the controller edits the commentary and then accepts,
   **Then** the accepted text reflects the edit.
3. **Given** a card, **When** the controller dismisses it, **Then** the API is called and the card
   moves to dismissed (settled, de-emphasized) and is no longer an open item; progress updates.
4. **Given** any action, **When** the API returns the new state, **Then** the card's displayed
   status matches the API's review state.

---

### Edge Cases

- **Investigation in flight**: while a synchronous investigation runs (a few seconds), the card
  shows the investigating state and its actions are disabled until it resolves.
- **Failed investigation / API error**: surfaced on the affected card (or as a non-blocking
  notice); the workspace does not crash and other cards remain usable.
- **Invalid action for current status** (e.g. accept while still awaiting): the UI only offers
  actions valid for the card's status; if the API rejects an action, the card shows the API's
  current status rather than a stale optimistic one.
- **Empty queue**: when there are no flagged variances, the grid still renders and the queue shows
  an explicit empty state.
- **Edit then dismiss**: editing then dismissing settles the card as dismissed; the edit is not
  lost server-side (provenance lives in the API).
- **Long commentary / question text**: cards accommodate multi-line text without breaking layout.
- **Re-investigate**: where the API allows re-running (e.g. from drafted), the card offers it; the
  card reflects the resulting fresh state.
- **Stale view**: after any action, the card reflects the status the API returned; progress is
  recomputed from API state, never guessed by the UI.

## Requirements *(mandatory)*

### Functional Requirements

**Rendering from API data (no computation)**

- **FR-001**: The workspace MUST render the P&L grid — reporting lines, scenario columns, variance
  columns, subtotals, and margin sub-rows — from the API's served P&L in the served layout order.
- **FR-002**: The workspace MUST render one variance card per served flagged variance, and a
  progress indicator showing the API's resolved-of-total.
- **FR-003**: The UI MUST display every financial figure using the deterministic, display-ready
  formatted string the API serves (e.g. "€78,600.00", "16.7%") and MUST NOT perform any arithmetic
  on a figure — no adding, subtracting, multiplying, dividing, rounding, or re-deriving (including
  no ×100 for percent). The UI MAY apply non-value-changing styling (color, weight, alignment) but
  MUST NOT alter the served numeric text.
- **FR-003a**: (Mechanism for FR-003.) This feature depends on Block 4 exposing a deterministic
  display string per figure (formatted by Python), served from dedicated view endpoints so the raw
  endpoints stay byte-pure. If a figure is served only as a raw value, the UI displays it verbatim
  rather than reformatting it via arithmetic.
- **FR-004**: Lines with open agent items (flagged variances not yet resolved) MUST carry a visible
  marker in the grid.

**Anchoring & time cut**

- **FR-005**: Anchoring MUST be bidirectional. There is one card per flagged variance, and a
  reporting line may have several. Selecting a marked grid line MUST focus/scroll to and group the
  queue to that line's cards; selecting a card MUST highlight its corresponding grid line.
- **FR-006**: The workspace MUST provide a time-cut selector (prior-month YTD, current month, YTD,
  full year) that switches which cut the grid displays, using already-served data without
  recomputation.

**Lifecycle reflection per card**

- **FR-007**: Each card MUST display its variance and current status — detected, investigating,
  awaiting-controller, drafted, accepted, or dismissed — with a distinct visual treatment per
  status, always matching the API's review state.
- **FR-008**: An awaiting-controller card MUST show the agent's question and stated hypothesis and
  an input with a submit action for the controller's answer.
- **FR-009**: A drafted card MUST show the proposed commentary with accept, edit, and dismiss
  actions.
- **FR-010**: Accepted and dismissed cards MUST settle into a de-emphasized state with the accepted
  commentary text visible (for accepted).

**Actions through the API**

- **FR-011**: Triggering an investigation, submitting an answer, accepting, editing, and dismissing
  MUST each call the Block 4 API, and the UI MUST update the card's displayed state to match the
  API's response.
- **FR-011a**: Investigations MUST be triggerable per card on demand; the workspace MUST also
  provide a single "investigate all" action that runs the pending investigations sequentially.
  Investigations MUST NOT auto-run on load.
- **FR-012**: The UI MUST only offer actions that are valid for a card's current status; if the API
  rejects an action, the UI MUST display the API's returned status rather than a stale state.
- **FR-013**: Editing a draft before accepting MUST be supported, and the accepted result MUST
  reflect the controller's edit (as returned by the API).
- **FR-014**: After any action, the progress indicator MUST reflect API state (resolved/total),
  never a UI-guessed count.

**In-flight & errors**

- **FR-015**: While a live investigation runs, the affected card MUST show an investigating
  in-progress state and disable conflicting actions until it resolves.
- **FR-016**: A failed investigation or API error MUST be surfaced (on the card or as a
  non-blocking notice) without crashing the workspace; other cards MUST remain usable.

**Visual direction**

- **FR-017**: The interface MUST present a clean, modern finance/analytics aesthetic: light
  surfaces, generous spacing around a dense data grid, a single confident accent color, and
  semantic colors for variance direction (favorable/unfavorable) and card status.
- **FR-018**: The interface MUST NOT use a terminal/developer aesthetic: no dark console styling and
  no monospace type for content; financial numbers MUST align using tabular (lining) figures in a
  sans-serif typeface.

**Composition**

- **FR-019**: The UI MUST obtain all P&L, variance, investigation, progress, and accepted-commentary
  data from the Block 4 API (configurable base URL) and MUST hold no financial logic of its own.

### Key Entities *(include if feature involves data)*

- **Workspace View**: the full screen — grid pane, queue pane, time-cut selector, progress.
- **P&L Grid**: rows = reporting lines (regular, subtotal, margin sub-row) in served order; columns
  = scenario and variance values for the selected time cut; each figure is the API's served
  display string, rendered verbatim (never computed or reformatted).
- **Grid Line Marker**: a visible indicator on lines that have an open (unresolved) flagged variance.
- **Variance Card**: one per flagged variance (a reporting line may map to several) — its variance
  figures, current status, and the status-appropriate content (question + hypothesis, draft
  commentary + actions, or settled text).
- **Card Status**: detected | investigating | awaiting-controller | drafted | accepted | dismissed,
  mirroring the API.
- **Anchor Selection**: the currently focused line/card linking the two panes.
- **Time Cut**: prior-month YTD | current month | YTD | full year — the displayed grid cut.
- **Progress Indicator**: resolved count of total, from the API.
- **Answer Input**: the controller's typed answer to a question.
- **Edit Buffer**: the controller's in-progress edit of a draft before accept.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of financial figures displayed (grid cells and card values) equal the API's
  served display string character-for-character — the UI computes and reformats none, verified by
  comparing rendered text to the API response.
- **SC-002**: Card status matches the API's review state for 100% of cards at all times; after any
  action the displayed status equals the API's returned status.
- **SC-003**: Bidirectional anchoring works in 100% of tested cases — selecting a marked line
  focuses its card and selecting a card highlights its line.
- **SC-004**: Each of the controller actions (investigate, answer, accept, edit, dismiss) results in
  a corresponding API call and a UI state that matches the API response, in 100% of tested flows.
- **SC-005**: An edited-then-accepted draft shows the edited text as the accepted commentary in
  100% of tested cases.
- **SC-006**: A failed investigation or API error is surfaced without crashing the workspace in
  100% of tested failure cases; other cards remain usable.
- **SC-007**: The investigating in-progress state is visible for the duration of a live
  investigation call in 100% of tested triggers.
- **SC-008**: The progress indicator equals the API's resolved/total after every action in 100% of
  tested cases.
- **SC-009**: The interface uses no monospace type for content and aligns financial numbers with
  tabular figures, with semantic colors present for variance direction and card status — verified
  against the visual-direction checklist (0 terminal-aesthetic violations).
- **SC-010**: A controller can complete a full review of one variance (open → investigate → answer
  or draft → accept/edit/dismiss) without leaving the workspace screen.

## Assumptions

- **Consumes Block 4 only**: the UI talks exclusively to the Block 4 API at a configurable base URL;
  it holds no engine/agent logic and no financial computation. Out-of-scope screens (config,
  data-source/import, report export) are separate features.
- **Single-user, local, no auth (v0)**: matching Block 4 v0; the actor is the single controller.
- **Per-variance, manual investigation trigger + "investigate all"**: the controller triggers each
  variance's investigation on demand (live calls take a few seconds); a single "investigate all"
  action runs the pending ones sequentially. Investigations never auto-run on load.
- **Synchronous investigations**: Block 4 v0 runs investigations synchronously, so the investigating
  state is shown while the request is in flight and the response yields the final status; no polling
  is required, and the design does not preclude a future asynchronous/polled model.
- **Time cut is a view selector**: the served P&L contains all cuts; switching the time cut filters
  which columns the grid shows and never recomputes a figure.
- **Display strings come from the API**: Block 4 serves a deterministic, display-ready formatted
  string per figure (formatted by Python); the UI renders it verbatim and applies only
  non-value-changing styling (color, weight, alignment). The UI performs no ×100, rounding, or
  summing. (Dependency: a small Block 4 enhancement to expose figure display strings.)
- **Desktop-first**: a desktop analyst layout is assumed for v0; responsive/mobile is not required.
- **Mock data only**: the API runs on the fixture repository (Constitution Principle VIII); the UI
  shows whatever the API serves.

## Out of Scope

- Config editing (P&L layout, mappings, thresholds, agent settings).
- Data-source / import screens and real connector management.
- The report export / assembly view.
- Authentication, authorization, and multi-user concerns.
- Any computation or alteration of financial figures in the UI.
- Offline use; the UI requires the Block 4 API.
