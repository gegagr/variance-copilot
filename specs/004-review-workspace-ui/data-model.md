# Phase 1 Data Model: Review Workspace UI (Block 5)

The UI holds no domain models of its own — server data is the Block 4 contract (types **generated**
from `/openapi.json`). This document covers (a) the small Block 4 addition the UI depends on, and
(b) the UI view-models / state.

## A. Block 4 addition — figure display strings (dependency)

Deterministic Python owns number formatting (`engine/format.py`); Block 4 attaches display strings
to its served DTOs. Raw values stay for provenance/keys; the UI renders only the display strings.

### engine/format.py (pure, tested)

| Function | Input | Output example |
|----------|-------|----------------|
| `money(value, currency="EUR")` | `Decimal` | `"€78,600.00"` (grouping, 2dp, glyph) |
| `percent(ratio)` | `Decimal` | `"16.7%"` (ratio×100 in Python, 1dp) |
| `points(ratio)` | `Decimal` | `"+1.8 pp"` (signed, 1dp) |
| `not_meaningful(label)` | `str` | `"n/m"` |

These are the ONLY place a figure becomes a display string. (The engine already stores ratios;
`percent`/`points` do the ×100 in deterministic Python so the UI never does.)

### Block 4 view DTOs (api/schemas.py additions)

- **PnlCellView** — `{ value: str, display: str, value_kind: str, is_margin: bool }`. Served from
  the NEW `GET /pnl/view`; the raw `GET /pnl` stays byte-pure.
- **FlaggedVarianceView** — the served flag plus `current_display`, `comparator_display`,
  `abs_display`, `pct_display`, `pp_display` (nulls preserved). Served from the NEW
  `GET /variances/view`; the raw `GET /variances` stays byte-pure. Raw fields unchanged.
- **AcceptedCommentaryItem** already carries text; no figure display needed (commentary figures are
  already rendered strings from Block 3).

The OpenAPI schema reflects these, so the generated TS types include the display fields.

## B. UI view-models (`web/src/`)

### Generated API types (`api/types.ts`)
Mirror Block 4: `PnLResult`/`PnlCellView`, `FlaggedVarianceView`, `ReviewItemView`,
`InvestigationRecord`/`Question`/`Draft`, `ReviewProgressView`, `AcceptedCommentaryItem`,
`AnswerRequest`, `EditRequest`. Generated — not hand-edited.

### Query hooks (server state; `hooks/`)

| Hook | Endpoint(s) | Returns |
|------|-------------|---------|
| `usePnl(timeCut)` | `GET /pnl/view?current_period&time_cut` | P&L with display strings |
| `useVariances()` | `GET /variances/view?current_period` | `FlaggedVarianceView[]` |
| `useReview()` | `GET /review`, `GET /review/progress` | items + progress |
| `useAccepted()` | `GET /review/accepted` | accepted commentary (layout order) |
| `useReviewActions()` | the 5 POSTs | mutations; invalidate review/progress on success |

### UI state (local React, lifted to `Workspace.tsx`)

| State | Type | Purpose |
|-------|------|---------|
| `selectedFlagId` | `string \| null` | Anchoring focus (drives both panes). |
| `timeCut` | `"prior_month_ytd" \| "current_month" \| "ytd" \| "full_year"` | Grid cut. |
| `editBuffer` | `{ flagId: string, text: string } \| null` | In-progress draft edit before accept. |
| `investigateAllRunning` | `boolean` | Drives the sequential runner UI. |

No global state library; TanStack Query owns server data, these few fields own UI concerns.

### Derived structures (`lib/anchor.ts`, pure)

- `lineToFlags: Map<reporting_line, flag_id[]>` and `flagToLine: Map<flag_id, reporting_line>` —
  built from the variance list; drive bidirectional anchoring. A line may map to many flags.

## C. Card lifecycle → UI (mirrors Block 4 review status)

| Status (from API) | Card shows | Controls offered |
|-------------------|------------|------------------|
| `detected` | variance figures (display strings), "flagged" | **Investigate** |
| `investigating` | in-progress (pending) treatment | none (disabled) |
| `awaiting_controller` | the agent's Question + hypothesis + evidence | answer input + **Submit**; **Dismiss** |
| `drafted` | the proposed commentary | **Accept**, **Edit**, **Dismiss**; (re-investigate where allowed) |
| `accepted` | settled, de-emphasized; accepted text visible | **Edit** (reverts → drafted), **Dismiss** |
| `dismissed` | settled, de-emphasized | none |

Status comes from the API only; the UI never derives it. Controls are gated on status (FR-012);
the card always shows the API's returned status after an action.

## Validation & invariants (enforced by tests)

- **No figure arithmetic**: the UI renders `*_display` strings verbatim; a scan test forbids
  `parseFloat`/`Number(`/arithmetic on figures, and a render test asserts cell text === served
  `display` (SC-001).
- **Status mirrors API**: every card's displayed status equals the API's; after a mutation the
  refetch reconciles it (SC-002).
- **Anchoring**: selecting a line emphasizes its card group; selecting a card highlights its line
  (SC-003).
- **Actions**: each control fires the matching API call and the UI reflects the response (SC-004);
  edit-then-accept shows the edited text (SC-005).
- **Errors**: a failed investigation shows an error on that card without crashing the workspace
  (SC-006); the investigating state shows while pending (SC-007).
- **Progress**: equals API resolved/total after each action (SC-008).
- **Visual**: no monospace for content; numbers use `tabular-nums`; semantic colors present
  (SC-009).
