<!--
SYNC IMPACT REPORT
==================
Version change: (none) → 1.0.0
Bump rationale: Initial ratification of the Variance Copilot constitution. First
  formal adoption of all governing principles; no prior version existed.

Modified principles: N/A (initial adoption)

Added sections:
  - Core Principles (8 principles, all non-negotiable)
      I.    Determinism First
      II.   Auditability
      III.  LLM Scope Is Investigate-and-Draft Only
      IV.   Human in the Loop
      V.    Config-Driven, Not Hardcoded
      VI.   Source-Agnostic Data
      VII.  Excel and Word Export Are First-Class Outputs
      VIII. No Real Client Data in the Repository
  - Engineering Constraints
  - Development Workflow & Quality Gates
  - Governance

Removed sections: None

Templates requiring updates:
  - .specify/templates/plan-template.md   ⚠ pending (not yet present at project root;
      its "Constitution Check" gate MUST enumerate Principles I–VIII when generated)
  - .specify/templates/spec-template.md   ⚠ pending (not yet present; specs MUST
      declare config touchpoints and determinism boundaries when generated)
  - .specify/templates/tasks-template.md  ⚠ pending (not yet present; task categories
      MUST include determinism tests, export tasks, and config-vs-code separation)

Follow-up TODOs: None. Ratification date set to initial adoption date.
-->

# Variance Copilot Constitution

Variance Copilot is an AI-assisted P&L variance review tool for finance
controllers. A deterministic engine computes every number; an AI agent
investigates the general ledger behind flagged variances, asks the controller
targeted questions, and drafts the management commentary. The principles below
are binding and non-negotiable. They govern every spec, plan, and implementation
that follows, and they take precedence over convenience, speed, or any
conflicting instruction in a later spec.

## Core Principles

### I. Determinism First (NON-NEGOTIABLE)

Every financial figure — P&L lines, subtotals, margins, variances, percentages,
and percentage-point deltas — MUST be computed by deterministic Python. The LLM
MUST NEVER produce, estimate, round, reformat, or alter a number. If a number
reaches a screen, an export, or a report, a Python function created it and a test
can reproduce it exactly.

Rationale: Controllers sign their name to these numbers. A figure that an LLM
could have perturbed is a figure no one can defend. This principle is absolute
and MUST NEVER be relaxed, weakened, or scoped around by any later spec.

### II. Auditability (NON-NEGOTIABLE)

Every reported figure MUST trace back to the source transactions that produced
it. Every flagged variance MUST trace to an explicit, named rule whose thresholds
are defined in absolute-value, percentage, AND percentage-point terms. There are
no black-box flags and no unexplained numbers: given any figure or flag, the
system MUST be able to show what rule fired and which records contributed.

Rationale: An unexplainable flag is noise; an untraceable number is a liability.
Audit trails are what let a controller trust automation instead of re-checking it.

### III. LLM Scope Is Investigate-and-Draft Only (NON-NEGOTIABLE)

The agent's authority is strictly bounded. It MAY read GL detail through the
defined read-only tool (`query_gl_detail`), form hypotheses about variance
drivers, and ask the controller targeted questions. It MUST draft commentary only
from facts the controller has explicitly confirmed. It asks rather than asserts,
and it MUST NEVER invent context, fabricate drivers, or state an unconfirmed cause
as fact. The agent has no write access to financial data and no authority to
compute, change, or publish numbers.

Rationale: The model is an investigator and a drafter, not an oracle. Confining
it to read-and-ask removes the surface where hallucination becomes a reported fact.

### IV. Human in the Loop (NON-NEGOTIABLE)

No commentary enters the final report without explicit controller acceptance.
Every piece of agent output is a proposal, never auto-published. The controller
MUST be able to edit, accept, or dismiss every item individually. There is no path
by which agent text reaches leadership without a human acceptance step.

Rationale: The controller owns the narrative. Automation drafts; the human decides.
Auto-publishing would transfer accountability to a system that cannot hold it.

### V. Config-Driven, Not Hardcoded (NON-NEGOTIABLE)

P&L structure, chart-of-accounts mapping, business-unit hierarchy, and
entity/geography rollups MUST live in editable configuration files, never in code.
A controller MUST be able to restructure the P&L — re-map accounts, re-order lines,
change rollups — without touching Python. Code reads configuration; it does not
embed business structure.

Rationale: Org structures change every reorg and every acquisition. Structure baked
into code makes the tool brittle and forces an engineer into every finance change.

### VI. Source-Agnostic Data (NON-NEGOTIABLE)

All data access MUST go through a single repository interface. Supabase and CSV
import are interchangeable implementations behind one signature. The engine MUST
NEVER know or care which source it is reading; no module above the repository layer
may contain source-specific logic.

Rationale: Data lives in different places for different clients and stages. A clean
repository seam keeps the engine stable while the backing store is swapped freely.

### VII. Excel and Word Export Are First-Class Outputs (NON-NEGOTIABLE)

Leadership consumes Excel and Word. Export to both MUST be designed in from the
start as a core feature, never bolted on. Exports MUST carry the same deterministic
figures (Principle I) and the same audit traceability (Principle II) as the
on-screen view. Export fidelity is a release criterion, not a nice-to-have.

Rationale: A variance review that cannot leave the tool in the format leadership
reads is unfinished. Designing export last guarantees it fights the data model.

### VIII. No Real Client Data in the Repository (NON-NEGOTIABLE)

The repository MUST contain mock data only. A `.gitignore` MUST protect all real
inputs from ever being committed. The system MUST be fully reproducible: the same
inputs plus the same config MUST always produce the same outputs, and that
reproducibility MUST be exercised by tests.

Rationale: Real financial data in source control is a breach waiting to happen.
Reproducibility from mock data is also what makes the engine testable at all.

## Engineering Constraints

- **Language & computation**: All financial computation is implemented in
  deterministic Python (Principle I). No numeric logic may be delegated to the LLM.
- **Repository seam**: A repository interface (Principle VI) is the only path to
  data. `query_gl_detail` (Principle III) is the only GL-read surface exposed to
  the agent and MUST be read-only.
- **Configuration surface**: P&L structure, COA mapping, BU hierarchy, and
  entity/geography rollups are configuration artifacts (Principle V) and are
  versioned alongside code but kept separate from it.
- **Outputs**: On-screen view, Excel, and Word share one deterministic figure
  source and one audit trail (Principles I, II, VII).
- **Data hygiene**: Mock data only in the repo; real inputs are git-ignored
  (Principle VIII).

## Development Workflow & Quality Gates

- **Constitution Check**: Every plan and spec MUST include a Constitution Check
  that explicitly evaluates compliance with Principles I–VIII before
  implementation begins. A violation blocks the plan until resolved or, where the
  principle permits, justified.
- **Determinism tests**: Any feature touching figures MUST ship tests proving the
  same inputs + same config produce identical outputs (Principles I, VIII).
- **Traceability tests**: Any reported figure or flag MUST have a test asserting it
  traces to source records and, for flags, to a named threshold rule (Principle II).
- **Agent-boundary review**: Any change to the agent MUST be reviewed to confirm it
  neither computes numbers nor publishes commentary without controller acceptance
  (Principles III, IV).
- **Export parity**: Excel and Word exports MUST be validated for figure and audit
  parity with the on-screen view before release (Principle VII).

## Governance

This constitution supersedes all other practices and conventions. Where any spec,
plan, task, or instruction conflicts with a principle here, the principle wins.

- **Amendments**: Changes to this constitution MUST be proposed in writing,
  reviewed, and approved before adoption. Each amendment MUST update the version
  and the Sync Impact Report, and MUST propagate to dependent templates and docs.
- **Versioning policy** (semantic): MAJOR for backward-incompatible governance or
  principle removals/redefinitions; MINOR for a new principle or materially
  expanded guidance; PATCH for clarifications and non-semantic refinements. The
  five principles marked NON-NEGOTIABLE that form the product's core guarantees —
  Determinism First, Auditability, LLM Scope, Human in the Loop, and the data
  guarantees — MUST NOT be removed or weakened except by an explicit, justified
  MAJOR amendment; Determinism First (Principle I) MUST NEVER be relaxed at all.
- **Compliance review**: All reviews and merges MUST verify compliance with the
  Constitution Check. Unjustified complexity or any silent deviation from a
  principle is grounds to reject a change.
- **Runtime guidance**: Agent-specific and developer runtime guidance docs MUST
  remain consistent with this constitution; when a principle changes, those docs
  MUST be updated in the same amendment.

**Version**: 1.0.0 | **Ratified**: 2026-05-30 | **Last Amended**: 2026-05-30
