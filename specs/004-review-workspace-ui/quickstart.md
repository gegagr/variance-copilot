# Quickstart: Review Workspace UI (Block 5)

A React + TypeScript SPA (Vite) in `web/`, consuming the Block 4 API. All tests run offline with
Vitest + React Testing Library + MSW — no backend, no network, no key.

## Prerequisites

- Node 20+ and a package manager (pnpm/npm).
- For a *live* run: the Block 4 backend running locally (`uv run uvicorn api.main:app`), which needs
  `OPENROUTER_API_KEY` on the **backend** only — the frontend never sees it.

## One-time backend addition (dependency)

Block 4 must serve a display string per figure (constitutional anchor — see
[contracts/display-string.md](./contracts/display-string.md)): add `engine/format.py` and the
`*View` DTOs. Until then, the UI renders raw served values verbatim (still no UI arithmetic).

## Setup & run (live)

```bash
# 1) backend (separate terminal)
uv run uvicorn api.main:app --reload         # http://localhost:8000  (/docs, /openapi.json)

# 2) generate types from the live contract, then run the SPA
cd web
pnpm install
pnpm gen:api          # openapi-typescript http://localhost:8000/openapi.json -> src/api/types.ts
pnpm dev              # Vite dev server; proxies /api -> http://localhost:8000
```

Open the dev URL → the review workspace: P&L grid (left), variance queue (right), time-cut selector,
progress bar.

## A typical review flow (in the UI)

1. Open the workspace — flagged lines are marked; cards show `detected`.
2. Click **Investigate** on a card (or **Investigate all**) → the card shows `investigating`, then
   becomes a question or a draft.
3. For a question: read it, type an answer, **Submit** → the card returns a draft.
4. For a draft: **Accept**, **Edit** then accept, or **Dismiss** → progress updates.
5. Selecting a grid line focuses its card group; selecting a card highlights its line.

## Tests (offline)

```bash
cd web
pnpm test                         # Vitest + RTL + MSW
pnpm test VarianceCard.status     # controls per lifecycle status
pnpm test reviewFlow              # answer / accept / edit-then-accept / dismiss
pnpm test anchoring               # line <-> card selection
pnpm test noArithmetic            # the UI computes no figure
```

## The presentation-layer guarantee

- Every figure is rendered from the API's **display string** verbatim; `lib/format.ts` holds only
  display-side helpers that never alter a served figure, and `noArithmetic.test.ts` fails the build
  if a component does arithmetic on a figure.
- Card status is always the API's review state; mutations invalidate + refetch so the UI mirrors
  Block 4. Nothing is shown as final unless the API reports `accepted`.

## Safety

- The OpenRouter key stays on the backend; the frontend has no secrets and never calls the model.
- The UI requires the Block 4 API; it computes no financial figure of its own.
