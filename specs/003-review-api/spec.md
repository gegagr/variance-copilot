# Feature Specification: Review API Layer (Block 4)

**Feature Branch**: `003-review-api`

**Created**: 2026-05-31

**Status**: Draft

**Input**: User description: "Specify Block 4: the API layer. It exposes the deterministic P&L (Block 1), the flagged variances, and the AI investigation records (Block 3) to a client, and manages the controller's review workflow (accept / edit / dismiss). It is the composition root that wires the repository, engine, and agent together."

## Overview

Block 4 is the API and review-state layer. It is the composition root that wires the
repository, the deterministic engine (Block 1), and the AI investigation agent (Block 3)
together and exposes them to a client. It serves the P&L, the flagged variances, and the AI
investigation records, and it manages the controller's review workflow: running
investigations on demand, capturing answers to the agent's questions, and letting the
controller accept, edit, or dismiss drafted commentary.

This layer is deliberately thin. It preserves every guarantee of the layers beneath: it
performs no financial logic and never recomputes or alters a figure (Determinism First); it
never bypasses Block 3's traceability guard — all commentary originates from Block 3, which
already enforces that no number comes from the model; every commentary stays a proposal until
the controller explicitly accepts it (Human in the Loop); and every state-changing action is
explicit and logged (Auditability). v0 is single-user and local with no authentication; it
runs on the fixture repository and does not implement the web UI, real data connectors, or
report assembly.

## Clarifications

### Session 2026-05-31

- Q: What is the shape of "the API" (how does the future UI talk to it)? → A: A pure Python application-service core (orchestrates engine + agent + review state, fully testable offline) with a thin HTTP/JSON adapter on top as the UI contract — hexagonal, mirroring Block 3. Tests target the service core without a running server.
- Q: When the controller edits an already-ACCEPTED commentary, what happens to its status? → A: It reverts to `drafted` and must be explicitly re-accepted; nothing is final unless the exact text was accepted. Both the original AI draft and the edited text are retained.
- Q: Can a variance's investigation be re-run, and from which states? → A: Re-running is allowed from `detected` (e.g. after a fail-safe) or `drafted` (discarding the prior draft and returning to `investigating`); `awaiting-controller` must be answered first; `accepted`/`dismissed` cannot be re-run. A re-run replaces the prior InvestigationRecord.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Serve the P&L and flagged variances for a period (Priority: P1)

A client requests the management P&L for a chosen period and time cut (prior-month YTD,
current month, YTD, full year) and the flagged variances for that period. The API returns the
exact structured output the engine produced — scenarios plus variance columns, and the Block 1
FlaggedVariance list — with no figure recomputed or altered.

**Why this priority**: Without serving the P&L and flags there is nothing for the client to
display or review. This is the foundational read-through slice and is independently valuable.

**Independent Test**: Request the P&L and flags for a period; confirm the returned figures are
byte-for-byte identical to what the engine produces directly for the same inputs/config, and
that the flag list matches Block 1's output exactly.

**Acceptance Scenarios**:

1. **Given** a running API over the fixture repository, **When** a client requests the P&L for
   a period and time cut, **Then** the response contains the engine's structured P&L
   (scenarios + variance columns) with every figure identical to the engine's own output.
2. **Given** the same period, **When** a client requests the flagged variances, **Then** the
   response is exactly the Block 1 FlaggedVariance list for that period, unaltered.
3. **Given** any served figure, **When** it is compared to the engine output, **Then** the API
   has neither recomputed nor rounded it (the API holds no financial logic of its own).

---

### User Story 2 - Run and serve investigations with progressive status (Priority: P2)

A client triggers an AI investigation for a specific flagged variance. The variance's review
status moves from detected, to investigating, to either awaiting-controller (the agent posed a
question) or drafted (the agent produced a self-explanatory draft). The client can poll each
variance's status and retrieve the resulting InvestigationRecord, so it can show progressive
results per line.

**Why this priority**: Investigations are the core value the agent adds; running them per
variance on demand lets the client surface results progressively. Depends on US1's flags.

**Independent Test**: Trigger an investigation for one variance; confirm its status transitions
to investigating and then to awaiting-controller or drafted, and that the served
InvestigationRecord is exactly Block 3's output (question or draft) with its embedded evidence.

**Acceptance Scenarios**:

1. **Given** a flagged variance in status detected, **When** the client triggers its
   investigation, **Then** the variance transitions through investigating to either
   awaiting-controller (a Question) or drafted (a Draft), and the InvestigationRecord is served.
2. **Given** an investigation that produced a question, **When** the client retrieves the
   variance, **Then** its status is awaiting-controller and the served Question is exactly
   Block 3's Question (text, hypothesis, embedded evidence) — unaltered.
3. **Given** the agent fails to produce grounded output (Block 3 fail-safe), **When** the
   client retrieves the variance, **Then** the API reports the failure and the variance is not
   advanced to drafted (no ungrounded commentary is ever served).

---

### User Story 3 - Answer a question and receive the drafted commentary (Priority: P3)

For a variance awaiting the controller, the controller submits an answer to the agent's
question. The API passes the answer to Block 3, which drafts commentary, and returns the
resulting Draft. The variance moves to drafted.

**Why this priority**: Closing the question loop is what turns an open variance into a
reviewable draft. Depends on US2 having produced a question.

**Independent Test**: For a variance in awaiting-controller, submit an answer; confirm a Draft
is returned whose provenance records the controller's answer, every figure traces to source
(Block 3 guarantee), and the variance status becomes drafted.

**Acceptance Scenarios**:

1. **Given** a variance in status awaiting-controller, **When** the controller submits an
   answer, **Then** the API returns the Block 3 Draft built from that answer and the variance
   status becomes drafted.
2. **Given** a submitted answer, **When** the resulting Draft is inspected, **Then** its
   provenance records the controller's answer verbatim and every figure traces to a source
   value (the API neither adds nor alters any number).
3. **Given** a variance not in awaiting-controller, **When** an answer is submitted for it,
   **Then** the API rejects the action as an invalid lifecycle transition.

---

### User Story 4 - Accept, edit, or dismiss a draft (Priority: P4)

The controller reviews a drafted commentary and accepts it, edits it, or dismisses the
variance. Accepting marks the commentary final; editing preserves both the original AI draft
and the controller's edited text; dismissing removes the variance from the commentary set.
Each action updates the status and is recorded with who and when.

**Why this priority**: This is the Human-in-the-Loop core of the product — nothing becomes
final without an explicit accept. Depends on US2/US3 having produced a draft.

**Independent Test**: From a drafted variance, exercise accept, edit, and dismiss; confirm each
moves the status correctly, that an edit retains the original draft alongside the edited text,
that an accept is required before any commentary is treated as final, and that every action is
recorded with actor and timestamp.

**Acceptance Scenarios**:

1. **Given** a variance in status drafted, **When** the controller accepts it, **Then** its
   status becomes accepted and only then is the commentary treated as final.
2. **Given** a variance in status drafted, **When** the controller edits the commentary,
   **Then** both the original AI draft and the edited text are retained (provenance preserved)
   and the action is recorded; **Given** a variance in status accepted, **When** it is edited,
   **Then** it reverts to drafted and must be re-accepted before its commentary is final again.
3. **Given** a variance, **When** the controller dismisses it, **Then** its status becomes
   dismissed and it is excluded from the accepted-commentary set.
4. **Given** any state-changing action (answer, accept, edit, dismiss), **When** it occurs,
   **Then** it is recorded with the actor and a timestamp.
5. **Given** an action that is not valid for the current status, **When** it is attempted,
   **Then** the API rejects it and the status is unchanged.

---

### User Story 5 - Serve review progress and accepted commentary in layout order (Priority: P5)

A client requests overall review progress (how many variances are resolved out of the total)
and the set of accepted commentary, ordered by the P&L layout, ready for the later report
layer to consume.

**Why this priority**: Progress and the assembled accepted set are what make the review
"done" and feed the report block. Depends on US4's accepted/dismissed states.

**Independent Test**: With a known mix of accepted, dismissed, and open variances, request
progress and the accepted set; confirm the resolved count equals accepted plus dismissed, and
that the accepted commentary is returned in P&L-layout order.

**Acceptance Scenarios**:

1. **Given** a set of variances with mixed statuses, **When** progress is requested, **Then**
   the resolved count equals the number accepted plus dismissed, out of the total flagged.
2. **Given** several accepted commentaries, **When** the accepted set is requested, **Then**
   they are returned ordered by their reporting line's P&L-layout order, each carrying its
   provenance.
3. **Given** a dismissed variance, **When** the accepted set is requested, **Then** the
   dismissed variance does not appear.

---

### Edge Cases

- **Persistence across restart**: review state (statuses, answers, accepted/edited/dismissed
  drafts, action history) survives process restart; a client sees the same state after a
  restart.
- **Re-triggering an investigation**: allowed from detected or drafted (a re-run replaces the
  prior InvestigationRecord and returns the item to investigating); rejected from
  awaiting-controller (the question must be answered first), accepted, or dismissed.
- **Answering an already-answered question**: rejected as an invalid transition (the variance
  is no longer awaiting-controller).
- **Accepting a variance that has no draft** (still detected / awaiting-controller): rejected.
- **Editing after accept**: allowed; the item reverts to drafted and must be re-accepted; the
  edit is recorded and both the original AI draft and the edited text are retained; an empty edit
  (no change) is recorded but does not lose the original.
- **Dismiss is reversible only via the defined lifecycle** (if at all); the spec's lifecycle
  governs whether a dismissed item can be re-opened.
- **Agent fail-safe**: when Block 3 returns no grounded output, the variance stays in a
  non-drafted state and the API surfaces the failure; it never fabricates commentary.
- **Unknown period / variance id**: the API returns a clear not-found result, not a partial or
  invented response.

## Requirements *(mandatory)*

### Functional Requirements

**Serving engine & agent output (thin, no recompute)**

- **FR-001**: The API MUST serve the management P&L for a requested period and time cut
  (prior-month YTD, current month, YTD, full year) as the engine's structured output —
  scenarios plus variance columns.
- **FR-002**: The API MUST serve the flagged variances for a period as Block 1's FlaggedVariance
  output, unaltered.
- **FR-003**: The API MUST NOT recompute, round, or alter any figure; it holds no financial
  logic of its own and serves the engine's and agent's values verbatim.
- **FR-004**: The API MUST run AI investigations over flagged variances via Block 3 and serve
  the resulting InvestigationRecords (Question or Draft) exactly as Block 3 produced them.
- **FR-005**: Investigations MUST be runnable per variance on demand so a client can present
  progressive results.

**Question/answer loop**

- **FR-006**: The API MUST accept a controller's answer to a variance's question and return the
  Block 3 Draft built from that answer.
- **FR-007**: The API MUST pass commentary drafting to Block 3 and MUST NOT generate, edit, or
  alter any figure in commentary itself; it never bypasses Block 3's traceability guard.

**Review lifecycle**

- **FR-008**: The API MUST track each flagged variance's review status as exactly one of:
  detected, investigating, awaiting-controller, drafted, accepted, dismissed.
- **FR-009**: Status transitions MUST follow the defined lifecycle:
  detected → investigating; investigating → awaiting-controller or drafted;
  awaiting-controller → drafted (on answer); drafted → accepted (accept), drafted → dismissed
  (dismiss); accepted → dismissed (dismiss). Editing is allowed on drafted or accepted; editing
  an **accepted** item reverts its status to **drafted** (the new text MUST be explicitly
  re-accepted before it is final), while editing a drafted item leaves it drafted. Re-running an
  investigation is allowed from detected or drafted (a re-run discards the prior draft and
  returns the item to investigating); it is NOT allowed from awaiting-controller (the question
  must be answered first), accepted, or dismissed. Dismiss is allowed from detected,
  awaiting-controller, drafted, or accepted. Any transition not defined MUST be rejected.
- **FR-010**: The API MUST expose actions to accept, edit, and dismiss a draft, each updating
  the status per the lifecycle.
- **FR-011**: Accepting a variance MUST be the only way a commentary becomes final; until then
  every commentary is a proposal.
- **FR-012**: Editing a draft MUST preserve provenance: the original AI draft text and the
  controller's edited text MUST both be retained.

**Auditability**

- **FR-013**: Every state-changing action (answer, accept, edit, dismiss, and triggering an
  investigation) MUST be recorded with the actor ("who") and a timestamp ("when").
- **FR-014**: The action history for a variance MUST be retrievable for audit.

**Progress & assembled output**

- **FR-015**: The API MUST serve review progress: the number of resolved variances (accepted
  plus dismissed) out of the total flagged.
- **FR-016**: The API MUST serve the set of accepted commentary ordered by the reporting line's
  P&L-layout order, each item carrying its provenance, ready for the report layer.

**State persistence**

- **FR-017**: Review state — statuses, controller answers, accepted/edited/dismissed drafts, and
  action history — MUST persist so it survives across requests and process restarts (mechanism
  decided at the plan stage).

**Contract & composition**

- **FR-018**: The API surface (request/response shapes for every resource and action) MUST be
  documented so the UI block can build against it as a stable contract, exposed as a thin
  HTTP/JSON adapter over the service core.
- **FR-019**: The API MUST be structured as a pure Python application-service core (the
  composition root wiring the fixture Repository, the engine, and the agent) with a thin HTTP/JSON
  adapter on top; the service core MUST be fully testable offline without a running server. It
  MUST consume data only through the Repository abstraction (no source-specific logic) and MUST
  NOT depend on real data connectors in v0.
- **FR-020**: The API MUST return a clear not-found result for unknown periods or variance ids,
  never a partial or invented response.

### Key Entities *(include if feature involves data)*

- **Period Request**: the (period, time cut) a client asks the P&L/flags for.
- **P&L View** *(served)*: the engine's structured P&L for the request — scenarios + variance
  columns — passed through verbatim.
- **FlaggedVariance** *(served, from Block 1)*: the flag list for the period, unaltered.
- **InvestigationRecord** *(served, from Block 3)*: the per-variance Question or Draft with
  embedded evidence, unaltered.
- **ReviewItem**: the review state of one flagged variance — its flag id, current status, the
  latest InvestigationRecord, the controller's answer (if any), the accepted/edited commentary
  (if any), and its action history.
- **ReviewStatus**: one of detected, investigating, awaiting-controller, drafted, accepted,
  dismissed.
- **ControllerAnswer**: the controller's response to a question (verbatim), with actor + time.
- **EditedCommentary**: the controller's edited text plus a reference to the original AI draft
  (both retained).
- **ReviewAction (Audit Entry)**: a state-changing action — type (answer/accept/edit/dismiss/
  investigate), actor, timestamp, and the status before/after.
- **ReviewProgress**: total flagged, resolved (accepted + dismissed), and counts by status.
- **AcceptedCommentaryItem**: an accepted (possibly edited) commentary with its reporting line,
  layout order, text, and provenance — emitted in P&L-layout order.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of figures served by the API (P&L cells, variances, commentary figures) are
  identical to the engine's/agent's own output for the same inputs — the API alters no number,
  verified by comparison.
- **SC-002**: 0 commentaries are treated as final without an explicit accept; every non-accepted
  commentary is marked a proposal.
- **SC-003**: For 100% of edited drafts, both the original AI draft text and the controller's
  edited text are retrievable.
- **SC-004**: 100% of state-changing actions (answer, accept, edit, dismiss, investigate) have an
  audit record with actor and timestamp.
- **SC-005**: Every variance is always in exactly one defined status, and 100% of attempted
  invalid transitions are rejected with the status left unchanged.
- **SC-006**: Review progress equals accepted-plus-dismissed over total flagged for every tested
  mix of statuses (exact count match).
- **SC-007**: The accepted-commentary set is returned in P&L-layout order for 100% of tested
  cases, excluding dismissed variances.
- **SC-008**: Review state is identical before and after a process restart for 100% of tested
  states (persistence verified).
- **SC-009**: The API surface is documented such that a client can construct every request and
  validate every response against the published shapes (contract completeness).
- **SC-010**: When Block 3 returns no grounded output, the API never serves commentary for that
  variance (0 ungrounded commentaries surfaced).

## Assumptions

- **Single-user actor (v0)**: with no authentication, the "who" on every action is a single
  configured controller identity (e.g. "controller"). Multi-user attribution is out of scope.
- **Execution model**: investigations may run synchronously (the trigger blocks until Block 3
  returns) in v0, but the status lifecycle and a per-variance status read are exposed so the
  contract supports progressive/polled results and a future asynchronous implementation without
  changing the surface.
- **Period addressing**: a period is addressed by the engine's "current period" plus the
  requested time cut; the fixture data and config determine which periods exist.
- **Thin layer**: the API contains no financial computation; all figures come from the engine
  and all commentary from the agent. It orchestrates and stores review state only.
- **Persistence is a plan decision**: the spec requires durable review state; the concrete store
  (file/embedded DB) is chosen at the plan stage. It holds review state only — never a copy of
  recomputed figures.
- **Traceability preserved by delegation**: the API never generates commentary; because all
  commentary comes from Block 3 (which enforces the traceability guard), the API cannot
  introduce an ungrounded number.
- **Idempotent reads**: serving the P&L, flags, and investigation records does not mutate review
  state; only the explicit actions do.
- **Mock data only**: per the constitution, the API runs on the fixture repository; no real
  client data.

## Out of Scope

- The web UI.
- Real CSV/Supabase data connectors (v0 uses the fixture repository behind the Repository
  abstraction).
- Report assembly / export (Word/Excel generation from accepted commentary).
- Authentication, authorization, and multi-user concerns.
- Any recomputation or alteration of engine figures or agent commentary.
- Asynchronous job infrastructure beyond what the status lifecycle requires.
