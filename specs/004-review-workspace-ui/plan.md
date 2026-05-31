# Implementation Plan: Review Workspace UI (Block 5)

**Branch**: `004-review-workspace-ui` | **Date**: 2026-05-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/004-review-workspace-ui/spec.md`

## Summary

Block 5 is the controller's review workspace — a React + TypeScript single-page app (Vite) that
consumes the Block 4 API and renders exactly what it serves: the P&L grid, the variance review
queue, progress, and the per-variance lifecycle (investigate → answer → accept / edit / dismiss).

Technical approach: a thin **typed API client** (types generated from FastAPI's
`/openapi.json`) wrapped by **TanStack Query** hooks that own all server state; mutations
invalidate and refetch so the UI always mirrors the API's review state. Local React state holds
only UI concerns (the selected variance for anchoring, the chosen time cut). Components are built
from **shadcn/ui on Tailwind** with a light, finance-SaaS aesthetic (single indigo accent,
semantic variance/status colors, Inter with tabular figures — explicitly not a terminal). Per the
constitution at the presentation layer, **no component computes a figure**: every number is
rendered from the API's deterministic display string verbatim. Tests run offline with Vitest +
React Testing Library + MSW. The Python backend is untouched except for one small, constitutionally
required addition: Block 4 must expose a deterministic **display string per figure** (formatted by
Python) so the UI never reformats a number.

## Technical Context

**Language/Version**: TypeScript 5.x on Node 20+; React 18; Vite 5 (SPA, no SSR).

**Primary Dependencies**: React, Vite, Tailwind CSS, shadcn/ui (Radix primitives), TanStack Query
v5, a generated OpenAPI types module (e.g. via `openapi-typescript`). Dev/test: Vitest, React
Testing Library, MSW. Backend dependency: the Block 4 FastAPI app + its `/openapi.json`.

**Storage**: None in the UI. All data from the Block 4 API; the SQLite review state lives in
Block 4. No client persistence beyond TanStack Query's in-memory cache.

**Testing**: Vitest + React Testing Library; MSW mocks the Block 4 API deterministically/offline.
Component tests per lifecycle status; interaction tests for answer/accept/edit/dismiss; an
anchoring test; a "no-arithmetic" guard test.

**Target Platform**: Desktop browser (analyst layout). Vite dev server proxies `/api` to the local
FastAPI backend.

**Project Type**: Web frontend (`web/`) alongside the existing Python backend; the backend is
otherwise untouched.

**Performance Goals**: Not heavy; a dense grid (tens of lines) + a queue (tens of cards) render
instantly. Investigations are synchronous (a few seconds) and surface a pending state.

**Constraints**: The UI performs **no arithmetic on any financial figure** — it renders the API's
display strings verbatim (Determinism First at the presentation layer). Card status always mirrors
the API (no client-side lifecycle logic). The OpenRouter key never reaches the frontend. Not a
terminal aesthetic (no monospace for content, no dark console theme).

**Scale/Scope**: One screen (the workspace). ~6 component families. ~8 API operations behind typed
hooks. Single-user, local, no auth.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | How this plan complies | Status |
|---|-----------|------------------------|--------|
| I | Determinism First | The UI renders the API's **deterministic display string** per figure verbatim and contains **no figure arithmetic** (a guard test forbids `*`,`/`,`Number()`,`parseFloat` on served figures and asserts rendered text === API display string). All numbers (incl. formatting) are produced by Python in the deterministic layers. | ✅ PASS |
| II | Auditability | Every controller action is a Block 4 API call (which logs it). The UI adds no unlogged state change; it reflects API state only. | ✅ PASS |
| III | LLM Scope | The UI triggers investigations through Block 4; it never calls the model, generates commentary, or expands the agent's authority. | ✅ PASS |
| IV | Human in the Loop | The UI is the accept/edit/dismiss surface; commentary is shown as a proposal until the API reports `accepted`. Card status mirrors the API; invalid actions aren't offered, and a rejected action shows the API's returned status. | ✅ PASS |
| V | Config-Driven | The API base URL and the visual theme tokens are config; no business structure in the UI. Layout/figures come from the API (which reads Block 1 config). | ✅ PASS |
| VI | Source-Agnostic Data | The UI depends only on the Block 4 HTTP contract (typed from OpenAPI); it has no knowledge of the repository or data source beneath. | ✅ PASS |
| VII | Excel & Word Export First-Class | N/A (report export view is out of scope); the accepted-commentary surface is served by Block 4 for the future report layer. | ✅ N/A |
| VIII | No Real Client Data | The UI shows whatever the API serves (mock fixtures in v0); it stores no real data and holds no secrets (the OpenRouter key stays on the backend). | ✅ PASS |

**Result**: PASS. The one design implication — Block 4 must serve a display string per figure — is
recorded as a dependency (research R1) so the UI never reformats a number. No violations →
Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/004-review-workspace-ui/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (UI view-models + the Block 4 display-string addition)
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── api-consumption.md       # which Block 4 endpoints the UI calls + the generated-types flow
│   ├── display-string.md        # the Block 4 figure display-string contract (the dependency)
│   └── ui-states.md             # card lifecycle → controls/visual matrix
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root — a new `web/` alongside the untouched backend)

```text
web/
├── index.html
├── package.json
├── vite.config.ts               # dev proxy /api -> FastAPI; Vitest config
├── tailwind.config.ts           # theme tokens: indigo accent, semantic colors, Inter
├── tsconfig.json
├── openapi-types.config         # generation config (FastAPI /openapi.json -> src/api/types.ts)
├── src/
│   ├── main.tsx                 # app entry; QueryClientProvider
│   ├── App.tsx                  # Workspace shell (two panes)
│   ├── api/
│   │   ├── types.ts             # GENERATED from /openapi.json (do not hand-edit)
│   │   └── client.ts            # thin typed fetch wrapper (the only network access)
│   ├── hooks/
│   │   ├── usePnl.ts            # P&L for a cut
│   │   ├── useVariances.ts      # flagged variances
│   │   ├── useReview.ts         # review items + progress + accepted
│   │   └── useReviewActions.ts  # investigate / answer / accept / edit / dismiss mutations
│   ├── components/
│   │   ├── Workspace.tsx        # owns selected-variance + time-cut UI state; anchoring
│   │   ├── PnlGrid.tsx          # row variants: line / subtotal / margin; flagged markers
│   │   ├── TimeCutSelector.tsx
│   │   ├── ProgressBar.tsx
│   │   ├── VarianceReviewPanel.tsx  # the queue
│   │   ├── VarianceCard.tsx     # variant per lifecycle status
│   │   └── ui/                  # shadcn/ui primitives
│   ├── lib/
│   │   ├── format.ts            # DISPLAY-ONLY helpers (never touch figure strings)
│   │   └── anchor.ts            # line <-> cards index (one card per flag; group by line)
│   └── styles/
│       └── index.css            # Tailwind layers; tabular-nums utility
└── tests/
    ├── setup.ts                 # RTL + MSW server
    ├── msw/handlers.ts          # deterministic Block 4 API fixtures
    ├── VarianceCard.status.test.tsx     # controls per lifecycle status
    ├── reviewFlow.test.tsx              # answer / accept / edit-then-accept / dismiss (MSW)
    ├── anchoring.test.tsx               # line <-> card selection
    ├── pnlGrid.test.tsx                 # renders served display strings; markers
    └── noArithmetic.test.ts             # guard: UI computes no figure

# Backend addition (Block 4) required by this UI — minimal, constitutional:
api/ (Block 4)                   # add a deterministic display string per figure to served DTOs
```

**Structure Decision**: A standalone `web/` SPA that depends only on the Block 4 HTTP contract.
TanStack Query owns all server state; `Workspace.tsx` lifts the two pieces of genuine UI state
(selected variance, time cut) and drives bidirectional anchoring via a `line ↔ cards` index
(`lib/anchor.ts`). The typed client (`api/client.ts`) is the single network seam, using types
**generated** from `/openapi.json` so the frontend cannot drift from the Block 4 contract.
`lib/format.ts` holds display-only helpers that never alter a served figure string — and a guard
test enforces it. The Python backend is untouched **except** for the small, constitutionally
required addition of a per-figure display string in Block 4's served DTOs (see research R1 /
contracts/display-string.md), which keeps all number formatting in the deterministic Python layer.

## Complexity Tracking

> No constitution violations. No entries required.
