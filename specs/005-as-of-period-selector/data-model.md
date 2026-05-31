# Phase 1 — Data Model: As-of Period Selector

This feature adds **one dimension** — the as-of month `current_period` — to the review-state model
and threads it through the store. It introduces **no new financial data and stores no figure**;
P&L/variance figures remain computed by the engine on demand. Block 1 contracts are untouched.

## Entities

### As-of month (`current_period`)
- **What it is**: The fiscal month (1–12) the workspace is anchored to — the single source of truth
  selecting which month's P&L, variances, and review queue are shown.
- **Type**: `int`, validated `1 ≤ current_period ≤ 12` at every route (`Query(ge=1, le=12)`).
- **Selectable set**: the months that have actuals (periods 1–6 in the current mock dataset);
  default = latest = 6.
- **Provenance**: an explicit user input at every layer; **never** derived from the wall clock.
- **Not stored as data**: it is a request parameter and a store key — not a persisted figure.

### ReviewItem (re-keyed)
The existing review-state record, now identified per month.

| Field | Type | Change | Notes |
|-------|------|--------|-------|
| `current_period` | `int` | **NEW** | Part of the identity; which as-of month this item belongs to |
| `flag_id` | `str` | unchanged | Flag identity within the month |
| `reporting_line` | `str` | unchanged | |
| `status` | `ReviewStatus` | unchanged | detected / investigating / awaiting_controller / drafted / accepted / dismissed / failed |
| `record` | `InvestigationRecord?` | unchanged | immutable agent snapshot |
| `original_draft` | `Draft?` | unchanged | provenance retained on edit |
| `controller_answer` | `ControllerInput?` | unchanged | |
| `edited_text` | `str?` | unchanged | |
| `error` | `str?` | unchanged | failure reason when `status == failed` |
| `created_at` / `updated_at` | `str` | unchanged | ISO timestamps |

- **Identity**: `(current_period, flag_id)` — the same `flag_id` in two months is two independent
  items.
- **Embedded contract models** (`InvestigationRecord`, `Draft`, `ControllerInput`) remain immutable
  JSON snapshots — the store still never decomposes a figure into numeric columns, so it cannot alter
  one.

### ReviewAction (period-scoped)
Append-only audit entry for each state change.

| Field | Type | Change | Notes |
|-------|------|--------|-------|
| `current_period` | `int` | **NEW** | Which month's item changed |
| `action_id` | `str` | unchanged | unique, ordered |
| `flag_id` | `str` | unchanged | |
| `action` | `ReviewActionType` | unchanged | investigate / answer / accept / edit / dismiss |
| `actor` | `str` | unchanged | controller id |
| `ts` | `str` | unchanged | ISO timestamp |
| `from_status` / `to_status` | `ReviewStatus` | unchanged | |
| `payload` | `dict?` | unchanged | e.g. error reason, edited text |

- **Scope**: actions are queried per `(current_period, flag_id)` for history.

### Review queue (per month) — derived
- The collection of `ReviewItem`s for one `current_period`. Not a stored aggregate; it is
  `store.list_all(current_period)` after idempotent seeding of that month's flags.

## State transitions (unchanged)

The lifecycle state machine is identical to Block 4; only its scope narrows to a single month:

```
detected ──investigate──▶ investigating ──▶ awaiting_controller ──answer──▶ drafted ──accept──▶ accepted
   ▲                          │                                              │  ▲                  │
   │                          └────────────▶ drafted (self-explanatory)      │  └──edit────────────┘
   │                          └────────────▶ failed (no grounded record)     │
   └──────────────────────────────── (per current_period) ──────────────────┘   dismiss ─▶ dismissed
```

- Transitions, `RESOLVED = {accepted, dismissed}`, and the `failed` handling are unchanged.
- Per-month isolation: a transition on `(p, flag)` never affects `(p', flag)`.

## Store port (period-aware) — see contracts/review-store-port.md

```
get(current_period, flag_id)            -> ReviewItem | None
upsert(current_period, item)            -> None        # item carries current_period
list_all(current_period)                -> list[ReviewItem]
append_action(action)                   -> None        # action carries current_period
actions_for(current_period, flag_id)    -> list[ReviewAction]
```

## Validation rules
- `current_period` MUST be within `1..12` (else HTTP 422). A period in range with no actuals returns
  an empty queue (zero flags), never a substituted month.
- Seeding is idempotent: an existing item under `(current_period, flag_id)` is never overwritten or
  reverted by a read; only missing items are inserted as `detected`.
- For a fixed `current_period` and unchanged inputs/config, the flag set is identical every time —
  so `/variances`, `/review`, and `/review/progress` always report the same flags for that month.

## What is explicitly NOT in the data model
- No stored P&L figures, variances, margins, or percentages — all computed by the engine on demand.
- No new engine/Block 1 models or config schema changes.
- No change to `FlaggedVariance`, `InvestigationRecord`, `Draft`, or any versioned contract shape.
