# Implementation Plan: As-of Period Selector (single source of truth for current_period)

**Branch**: `005-as-of-period-selector` | **Date**: 2026-05-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-as-of-period-selector/spec.md`

## Summary

Make the **as-of month (`current_period`)** a single, user-selected value that threads identically
through the existing Block 4 API and Block 5 UI, and fix the bug where the review queue is empty
because the grid and the review store read different as-of months.

This is an **extension, not a rebuild**. The deterministic engine already takes `current_period`
as an explicit input (the CLI and `/pnl` / `/variances` already pass it); the work is to (1) thread
the *same* `current_period` through `/review` and `/review/progress` (and the mutation routes, so
each action targets the right per-period item), (2) key the existing `ReviewStore` by
`(current_period, flag_id)` so each as-of month owns its own queue and state, with idempotent
per-period seeding on first `/review`, and (3) add an "As of" selector to the existing Workspace
shell and put `current_period` into the existing TanStack Query keys so the grid, variances, and
review queue refetch together. The existing `time_cut` selector keeps working and slices relative to
the chosen as-of month.

The API still **computes no financial figure** — every number comes from the engine verbatim. The
only thing that changes is *which* deterministic month is selected and that all layers agree on it.
Block 1 numbers are untouched.

## Technical Context

**Language/Version**: Python 3.12+ (backend) reused as-is; TypeScript 5.x / React 18 / Vite 5 (web).

**Primary Dependencies**: Existing — FastAPI, Pydantic v2, SQLAlchemy/SQLite (`ReviewStore`),
pandas/Decimal engine; React, TanStack Query v5, Tailwind, generated OpenAPI types. No new deps.

**Storage**: The existing git-ignored SQLite review DB (`build/review.db`). Its primary key changes
from `flag_id` to `(current_period, flag_id)`, so the table is recreated (see research R3). Engine
figures remain file/config-sourced through the repository; no figure is stored.

**Testing**: pytest (backend) — extend the existing API/service/store suites; Vitest + RTL + MSW
(web) — extend the existing handlers/tests. All offline, deterministic, no live API/LLM.

**Target Platform**: Local FastAPI backend + Vite SPA, single-user, no auth (unchanged).

**Project Type**: Web app — existing `web/` SPA over the existing Python backend. Both extended in
place.

**Performance Goals**: Unchanged. Switching the as-of month refetches three queries for one month;
trivial at this scale (tens of lines, tens of cards).

**Constraints**: `current_period` is an explicit input at every layer, **never the wall clock**
(Determinism First). The API recomputes figures only by calling the engine — it constructs no
number itself. The OpenRouter key stays backend-only. The UI performs no figure arithmetic.

**Scale/Scope**: Backend — 4 read routes + 5 mutation routes gain a `current_period` parameter; the
`ReviewStore` port + 2 adapters + `ReviewService` re-keyed per period. Web — 1 new selector
component, query-key + hook signature changes, Workspace owns one new piece of UI state. No new
screens.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | How this plan complies | Status |
|---|-----------|------------------------|--------|
| I | Determinism First | `current_period` is an explicit, user-supplied input threaded unchanged through every layer — never derived from the clock. The API still calls the engine for every figure and computes nothing itself; flags come from `flag_variances` verbatim. Selecting a month changes *which* deterministic result is shown, not *how* any number is produced. | ✅ PASS |
| II | Auditability | Each state change still appends a `ReviewAction` (actor + timestamp); actions are now scoped to `(current_period, flag_id)` so the trail records which month's item changed. Flags still trace to their named threshold rule. | ✅ PASS |
| III | LLM Scope | Unchanged. The agent path is untouched; investigation still runs read-only `query_gl_detail` for the flag's own slice. The period parameter only routes which flag/item the existing flow targets. | ✅ PASS |
| IV | Human in the Loop | Unchanged. Lifecycle and accept/edit/dismiss are identical, just per-month. Nothing is final unless `accepted`. | ✅ PASS |
| V | Config-Driven | No business structure added to code. `current_period` is a runtime input; the set of selectable months is the months with actuals (data-derived). Thresholds/layout stay in config. | ✅ PASS |
| VI | Source-Agnostic Data | The `ReviewStore` **port** is extended (period-aware signatures) with both adapters (SQLite + in-memory) updated; the service still depends only on the abstraction. The engine reads through the existing repository unchanged. | ✅ PASS |
| VII | Excel & Word Export | N/A — export view out of scope. Per-period accepted commentary remains available for the future report layer. | ✅ N/A |
| VIII | No Real Client Data | Mock data only. The recreated review DB stays git-ignored; no real inputs introduced; same inputs + same config + same period → identical outputs (a determinism test asserts the flag set is stable per period). | ✅ PASS |

**Result**: PASS. No violations → Complexity Tracking empty. The one operational implication — the
review DB's primary key changes, so an existing `build/review.db` is recreated — is recorded as
research R3 (safe: the DB is dev-only, git-ignored, holds mock review state).

## Project Structure

### Documentation (this feature)

```text
specs/005-as-of-period-selector/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions (threading, store re-key, seeding, DB recreate, UI)
├── data-model.md        # Phase 1 — re-keyed ReviewItem/ReviewStore, period entity, no figure storage
├── quickstart.md        # Phase 1 — how to run/verify the bug fix and per-period isolation
├── contracts/           # Phase 1
│   ├── api-changes.md           # current_period parameter on read + mutation routes (no recompute)
│   ├── review-store-port.md     # period-aware ReviewStore port + SQLite/in-memory adapters + recreate
│   └── ui-changes.md            # As-of selector, query-key threading, hook signature changes
└── tasks.md             # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (existing files extended in place)

```text
# Backend (Block 4) — extended, no rebuild
api/
├── routes/
│   ├── pnl.py                  # /pnl, /variances already take current_period (unchanged shape)
│   ├── investigations.py       # /review + investigate/answer gain current_period (drop session default)
│   └── review.py               # /review/progress + accept/edit/dismiss/history/accepted gain current_period
├── services/
│   └── review_service.py       # remove _session_period; every method takes current_period
└── deps.py                     # unchanged composition; service no longer pins a session period

data/
├── review_store.py             # ReviewStore port + ReviewItem re-keyed by (current_period, flag_id);
│                               #   InMemoryReviewStore updated
└── sqlite_review_store.py      # composite PK (current_period, flag_id); both tables gain the column;
                                #   recreate-on-schema-mismatch (git-ignored DB)

engine/                         # UNTOUCHED (already current_period-driven). Block 1 numbers unchanged.

# Frontend (Block 5) — extended, no new screens
web/src/
├── api/
│   ├── schema.ts               # replace single CURRENT_PERIOD const with DEFAULT_PERIOD + AS_OF_PERIODS
│   └── client.ts               # review()/progress() + mutations pass ?current_period=
├── hooks/
│   └── api.ts                  # query keys include current_period; hooks take currentPeriod; mutations carry it
└── components/
    ├── Workspace.tsx           # owns currentPeriod state (default latest); threads into hooks + mutations
    └── AsOfSelector.tsx        # NEW — mirrors TimeCutSelector; lists periods with actuals

# Tests — extend existing suites (offline, deterministic)
tests/                          # API: consistent flag set across endpoints; queue non-empty @ p6;
                                #   per-period isolation; store keyed by (period, flag_id); idempotent seed
web/tests/                      # AsOfSelector refetch; query keys carry current_period (MSW param by period)
```

**Structure Decision**: Extend the existing hexagonal backend and TanStack-Query SPA in place. The
fix removes the implicit `_session_period` and makes `current_period` an explicit argument on every
service method and route, mirroring how `/pnl` and `/variances` already work. The `ReviewStore` port
gains a `current_period` dimension on its operations (both adapters updated, so the service still
depends only on the abstraction). On the web side, `current_period` becomes a piece of Workspace UI
state that participates in every query key — exactly the existing `time_cut` pattern — so the grid,
variances, and review queue always refetch together for one agreed month.

## Complexity Tracking

> No constitution violations. No entries required.
