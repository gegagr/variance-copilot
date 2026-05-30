# Feature Specification: AI Investigation and Commentary Layer (Block 3)

**Feature Branch**: `002-ai-investigation-commentary`

**Created**: 2026-05-30

**Status**: Draft

**Input**: User description: "Specify Block 3: the AI investigation and commentary layer. This layer turns the deterministic variance flags from Block 1 into explained management commentary. Per the constitution, the LLM investigates and drafts ONLY — it never produces, estimates, recomputes, or alters a number."

## Overview

Block 3 turns the deterministic variance flags produced by Block 1 into explained
management commentary. For each flagged variance, an AI agent investigates the general
ledger behind it, forms a hypothesis about the driver, and either drafts a commentary
line (when the evidence is self-explanatory) or poses a specific, evidence-grounded
question to the controller (when confirmation or context is needed). When the controller
responds, the agent combines the confirmed explanation with the GL evidence into a concise
management-commentary draft.

The agent's authority is strictly bounded (Constitution Principle III): it reads GL detail
through a defined read-only query, forms hypotheses, and asks or drafts — nothing more.
Every figure it references is taken verbatim from Block 1 output or a GL query result; the
agent never produces, estimates, recomputes, or rounds a number (Principle I). All output
is a proposal — accepting, editing, or dismissing is another layer's job (Principle IV).
Every LLM interaction is logged for audit (Principle II). This feature runs on the fixture
data and the Block 1 output; it does not implement the web UI, API, accept/edit/dismiss
actions, report assembly, or real data connectors.

## Clarifications

### Session 2026-05-30

- Q: How many question/answer rounds does the agent take per flag before drafting? → A: A single question round per flag — investigate → (Draft directly) or (one grounded Question → controller response → Draft). Multi-round back-and-forth is out of scope for this block.
- Q: How is the controller's response supplied in this block (no UI)? → A: Through a defined controller-input value passed into the draft step (programmatic / fixture-supplied); the UI that collects it is a separate layer.
- Q: How do figures get into the LLM's questions/drafts (enforcing the model never produces a number)? → A: Code substitutes by reference — the model selects figures/evidence by identifier and emits text with placeholders; deterministic code renders the actual values into the final string. The LLM never emits a digit; the traceability guard is a backstop.
- Q: Which figures are admissible in a question/draft (the guard's allowed set)? → A: Verbatim source values (the flag's Block 1 figures and that flag's GL amounts) PLUS deterministic code-computed aggregates over the flag's cited GL evidence (e.g. a sum of named rows), where the aggregate is computed and verified by code — never typed by the model.
- Q: How do the records reference the GL evidence they used? → A: Embed an immutable snapshot of the exact GL rows used (transaction id + fields) inside the InvestigationRecord / Question / Draft, so each record is self-contained and auditable even if the source later changes.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Investigate a flagged variance and gather grounded evidence (Priority: P1)

A controller has a list of flagged variances from Block 1. For one flag, the agent queries
the GL detail behind that reporting line / period / scenario, identifies the specific
transactions, projects, counterparties, dates, or labels that drive the variance, and forms
a hypothesis about the cause. It emits one InvestigationRecord linking the variance, the GL
evidence actually retrieved, the hypothesis, and a status (Question or Draft).

**Why this priority**: Without grounded investigation there is nothing to ask or draft from.
This is the foundational slice that converts a bare flag into evidence + a hypothesis, and
it is what makes every later question or draft defensible.

**Independent Test**: Feed one FlaggedVariance plus fixture GL data; confirm the agent
issues a GL query scoped to that flag's reporting line / period / scenario, the
InvestigationRecord cites the actual GL rows returned, the hypothesis references those rows,
and the record carries a Question-or-Draft status.

**Acceptance Scenarios**:

1. **Given** a flagged variance and fixture GL detail, **When** the agent investigates,
   **Then** it issues a read-only GL query scoped to that flag's reporting line, period, and
   scenario, and the resulting InvestigationRecord lists the GL evidence rows it used.
2. **Given** GL detail showing a single dominant transaction (e.g. one large project
   invoice), **When** the agent forms its hypothesis, **Then** the hypothesis names that
   specific evidence (transaction/project/counterparty/date/label), not a generic cause.
3. **Given** sparse or empty GL detail behind a flag, **When** the agent investigates,
   **Then** it records that no hypothesis could be formed rather than inventing a driver,
   and sets the status to Question.

---

### User Story 2 - Pose a specific, evidence-grounded question (Priority: P2)

When a variance is not self-explanatory, the agent poses one question to the controller.
The question is specific, grounded in the evidence it found, and states the agent's
hypothesis for the controller to confirm or correct — never a generic "why is this over
budget?". When evidence is too sparse to hypothesize, the question is open and honest about
the uncertainty.

**Why this priority**: The question is the agent's primary interaction with the controller
and the guardrail against hallucination — it asks rather than asserts. It depends on US1's
evidence and hypothesis.

**Independent Test**: For a flag whose evidence is ambiguous, confirm the emitted Question
references specific GL evidence, includes the stated hypothesis, and is not a generic
prompt; for a flag with sparse evidence, confirm the Question is open and explicitly signals
uncertainty rather than asserting a cause.

**Acceptance Scenarios**:

1. **Given** an InvestigationRecord with status Question and a formed hypothesis, **When**
   the agent produces the Question, **Then** the Question text states the hypothesis and
   references the specific supporting evidence rows.
2. **Given** an InvestigationRecord where no hypothesis could be formed, **When** the agent
   produces the Question, **Then** the Question is open ("we could not identify a clear
   driver from the ledger — can you add context?") and asserts no invented cause.
3. **Given** any produced Question, **When** it is inspected, **Then** it is specific to the
   flag (not a reusable generic template) and every figure in it traces to a Block 1 value
   or a GL query result.

---

### User Story 3 - Draft management commentary from confirmed input (Priority: P3)

For a self-explanatory variance, or once the controller has responded to a question, the
agent drafts a concise management-commentary line in a controller's register, combining the
confirmed explanation with the GL evidence. The Draft records its provenance: which
variance, which GL evidence, and which controller input (if any) it was built from.

**Why this priority**: The draft is the deliverable that feeds the eventual report. It
depends on US1's evidence and, when a question was posed, US2's question plus the
controller's response.

**Independent Test**: Provide an InvestigationRecord (Draft status, or Question status plus
a fixture controller response); confirm the agent emits a Draft whose text reflects the
evidence and confirmed explanation, whose provenance names the variance, the evidence rows,
and the controller input, and whose every figure traces to a source value.

**Acceptance Scenarios**:

1. **Given** an InvestigationRecord with status Draft (self-explanatory), **When** the agent
   drafts, **Then** it produces a Draft directly with no question, and the Draft's provenance
   records the variance and the GL evidence (controller input absent/empty).
2. **Given** an InvestigationRecord with status Question and a controller response, **When**
   the agent drafts, **Then** the Draft combines the confirmed explanation with the evidence
   and its provenance records the variance, the evidence, and the controller input verbatim.
3. **Given** any produced Draft, **When** it is inspected, **Then** every figure in the
   commentary traces to a Block 1 value or a GL query result, and the Draft is a proposal
   (it is not marked accepted/finalized).

---

### User Story 4 - Audit every LLM interaction (Priority: P4)

Every interaction with the language model is logged with the prompt sent, the response
received, the model identifier, and a timestamp, so any question or draft can be traced back
to the exact exchange that produced it.

**Why this priority**: Auditability (Constitution Principle II) is non-negotiable for a
tool a controller signs their name to. It is cross-cutting but is its own testable slice.

**Independent Test**: Run an investigation that triggers one or more model calls; confirm a
log entry exists per call with prompt, response, model identifier, and timestamp, and that
each emitted Question/Draft can be linked to its originating log entry.

**Acceptance Scenarios**:

1. **Given** an investigation that calls the model, **When** the call completes, **Then** a
   log entry records the full prompt, the full response, the model identifier, and a
   timestamp.
2. **Given** a produced Question or Draft, **When** it is inspected, **Then** it carries a
   reference linking it to the log entry/entries that produced it.

---

### Edge Cases

- **Sparse/empty GL detail**: the agent forms no hypothesis, sets status Question, and asks
  an open, honest question — it never invents a driver.
- **No flags**: given an empty flag list, the agent produces zero InvestigationRecords
  without error.
- **Multiple competing drivers**: when several transactions could explain the variance, the
  hypothesis names the dominant evidence and the question surfaces the ambiguity rather than
  asserting one cause.
- **Controller response that contradicts the hypothesis**: the Draft reflects the
  controller's correction, not the original hypothesis.
- **Controller response missing for a Question-status record**: no Draft is produced; the
  record remains at Question status (drafting is gated on a response).
- **A number appears in model text that is not in any source**: because the model emits
  references/placeholders (not digits), any stray literal number in model output is treated as
  a violation — the output fails the traceability guard and is rejected/flagged, never published.
- **Model unavailable or returns malformed output**: the agent records the failure in the
  audit log and surfaces it; it does not emit an ungrounded question or draft.

## Requirements *(mandatory)*

### Functional Requirements

**Investigation**

- **FR-001**: For each flagged variance, the agent MUST investigate by issuing a read-only
  GL query scoped to that flag's reporting line, period, and scenario.
- **FR-002**: The GL query interface MUST return the transaction rows behind a given
  reporting line / period / scenario, including account, amount, date, project,
  counterparty, and any labels, and MUST be read-only.
- **FR-003**: The agent MUST form a hypothesis about the variance driver from the retrieved
  evidence, naming specific transactions, projects, counterparties, dates, or labels.
- **FR-004**: The agent MUST decide, per flag, whether the variance is self-explanatory
  (status Draft) or requires controller confirmation/context (status Question).
- **FR-005**: The agent MUST produce exactly one InvestigationRecord per flag, working one
  variance at a time, so output maps to a per-line review workflow.
- **FR-006**: The agent MUST have access to the surrounding P&L context (the Block 1 result)
  so it can reason about the variance's relative magnitude.

**Questions**

- **FR-007**: When status is Question, the agent MUST pose one specific question grounded in
  the evidence it found, stating its hypothesis for the controller to confirm or correct.
- **FR-008**: A question MUST reference specific GL evidence and MUST NOT be a generic,
  reusable prompt (e.g. "why is this over budget?").
- **FR-009**: When GL detail is sparse or no hypothesis can be formed, the agent MUST ask an
  open, honest question that signals the uncertainty and MUST NOT invent a cause.

**Drafting**

- **FR-010**: For a self-explanatory variance, the agent MUST draft commentary directly,
  with no question.
- **FR-011**: When a controller response is supplied for a Question-status record, the agent
  MUST combine the confirmed explanation with the GL evidence into a concise
  management-commentary line written in a controller's register.
- **FR-012**: Drafting MUST be gated on a controller response for Question-status records: no
  Draft is produced until a response is supplied.
- **FR-013**: A Draft MUST record its provenance: the variance, the GL evidence rows, and the
  controller input (if any) it was built from.
- **FR-013a**: The InvestigationRecord, Question, and Draft MUST each embed an immutable
  snapshot of the exact GL evidence rows used (transaction id plus the fields cited), so each
  record is self-contained and auditable even if the underlying source later changes.

**Grounding & numbers (non-negotiable)**

- **FR-014**: The language model MUST NOT emit numeric digits in its generated text. It
  references figures and evidence by identifier (a Block 1 figure reference or a GL evidence
  row id) and emits placeholders; deterministic code renders the actual values into the final
  Question/Draft string. No number in any output originates from the model.
- **FR-014a**: (FR-014 forbids the model from typing any digit; this requirement defines what
  deterministic code is permitted to render.) Every figure rendered into a question or draft MUST be one of: (a) a value
  taken verbatim from Block 1 output or the flag's GL query result, or (b) a deterministic,
  code-computed aggregate over the flag's cited GL evidence rows (e.g. a sum or count of named
  rows). Aggregates MUST be computed and verified by code, never typed by the model. The agent
  MUST NOT generate, estimate, or round any number.
- **FR-015**: The feature MUST provide a testable traceability guard: each numeric value
  appearing in a final Question or Draft, when parsed, MUST either equal a verbatim source
  value (a Block 1 figure for that flag or an amount from the flag's GL query result) or equal
  a code-computed aggregate that the guard can independently recompute from the flag's cited
  GL evidence. Output containing any number that satisfies neither MUST be rejected rather than
  emitted.

**Human in the loop**

- **FR-016**: All agent output MUST be a proposal. This feature MUST NOT accept, edit,
  dismiss, finalize, or publish commentary — those actions belong to a separate layer.

**Auditability**

- **FR-017**: Every LLM interaction MUST be logged with the full prompt, the full response,
  the model identifier, and a timestamp.
- **FR-018**: Each emitted Question and Draft MUST carry a reference linking it to the LLM
  interaction log entry/entries that produced it.
- **FR-019**: When the model is unavailable or returns malformed/ungrounded output, the agent
  MUST record the failure in the audit log and MUST NOT emit an ungrounded question or draft.

**Contracts & data access**

- **FR-020**: The InvestigationRecord, Question, and Draft outputs MUST each be expressed as
  an explicit, versioned schema (a public contract, like Block 1's FlaggedVariance), so
  downstream layers can depend on them deliberately.
- **FR-021**: The agent MUST consume flags via the Block 1 FlaggedVariance schema and MUST
  access GL detail only through the defined read-only query interface (backed by the fixture
  repository in this block), with no dependency on a specific data source.

### Key Entities *(include if feature involves data)*

- **FlaggedVariance** *(input, from Block 1)*: the versioned flag record — reporting line,
  time cut, scenario pair, values, computed variance, and triggering rule.
- **GL Query**: a read-only request for the transaction detail behind a (reporting line,
  period, scenario).
- **GL Evidence Row**: one returned transaction — account, amount, date, project,
  counterparty, labels — used as evidence. An immutable snapshot of the rows used is embedded
  in the record that cites them (not merely referenced by id).
- **Rendered Figure**: a numeric value placed into output text by deterministic code — either
  a verbatim source value (Block 1 figure or GL amount) or a code-computed aggregate over
  cited evidence rows. The model references it by identifier; it never types the digits.
- **P&L Context**: the surrounding Block 1 result giving relative magnitude.
- **Hypothesis**: the agent's proposed driver, naming specific evidence; may be absent when
  evidence is too sparse.
- **InvestigationRecord** *(versioned output)*: per flag — the linked variance, the GL
  evidence used, the hypothesis (or its absence), and a status of Question or Draft, plus a
  link to the audit log.
- **Question** *(versioned output)*: question text, the stated hypothesis, and references to
  the supporting evidence; links to the audit log.
- **Controller Input**: the controller's response to a question (supplied programmatically in
  this block), captured verbatim for provenance.
- **Draft** *(versioned output)*: the drafted commentary text plus provenance — the variance,
  the GL evidence, and the controller input it was built from; links to the audit log.
- **LLM Interaction Log Entry**: prompt, response, model identifier, timestamp.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of numeric values appearing in emitted Questions and Drafts are either a
  verbatim source value (a Block 1 figure for that flag or an amount from the flag's GL query
  result) or a code-computed aggregate the guard can independently recompute from the flag's
  cited evidence — no untraceable or model-typed numbers — verified by an automated check.
- **SC-002**: 100% of emitted Questions reference at least one specific GL evidence row and
  contain no generic reusable template phrasing.
- **SC-003**: 100% of emitted Drafts record provenance naming the variance, the GL evidence,
  and the controller input (when a question was posed).
- **SC-004**: For self-explanatory variances, the agent produces a Draft with zero questions
  posed (no redundant questions), measured on a labeled fixture set.
- **SC-005**: For flags with sparse/empty GL detail, 100% of the time the agent asks an open
  question and records no invented driver (zero fabricated causes on the sparse-evidence
  fixtures).
- **SC-006**: 100% of LLM interactions have a log entry containing prompt, response, model
  identifier, and timestamp; and 100% of emitted Questions/Drafts link to their originating
  log entry.
- **SC-007**: The agent produces exactly one InvestigationRecord per input flag (count of
  records equals count of flags) and never finalizes/accepts commentary itself.
- **SC-008**: The InvestigationRecord, Question, and Draft outputs validate against their
  published versioned schemas for 100% of emitted records.

## Assumptions

- **Single question round**: per flag, the agent either drafts directly or asks one grounded
  question, receives one controller response, then drafts. Multi-round dialogue is out of
  scope for this block.
- **Controller response is supplied programmatically**: with no UI in this block, the
  controller's answer is provided as a defined input value to the draft step (fixture-supplied
  in tests). The UI that collects responses is a separate layer.
- **Enriched fixture GL detail**: the fixture GL data is extended with the fields the query
  contract requires (date, counterparty, labels) in addition to Block 1's account/amount/
  period/project tags. All such data is mock (Constitution Principle VIII).
- **GL query resolution**: a reporting line resolves to its GL accounts via the Block 1
  chart-of-accounts config; the query returns the matching fixture transactions for the given
  period and scenario.
- **Determinism of figures, not of prose**: the engine's numbers remain fully deterministic
  and the model emits no digits at all; the LLM's natural-language phrasing need not be
  byte-identical across runs, but every rendered number is inserted by deterministic code and
  is either a verbatim source value or a code-computed aggregate over cited evidence
  (FR-014/FR-014a/FR-015).
- **Model configuration**: the language model and its parameters are configuration; the
  specific provider/model is a planning decision and is recorded in the audit log per
  interaction (FR-017).
- **Scope of "controller's register"**: concise, factual, management-report tone; exact style
  guidance is a planning/prompt-design detail.

## Out of Scope

- The web UI and the API.
- Accept / edit / dismiss actions on questions and drafts.
- Final report assembly (Word/Excel report generation from accepted commentary).
- Real data connectors (Supabase or production GL sources); this block runs on the fixture
  repository.
- Re-computation or alteration of any Block 1 figure.
- Multi-round controller dialogue beyond a single question/response per flag.
