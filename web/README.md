# Variance Copilot — Review Workspace (Block 5)

React + TypeScript SPA (Vite) for the controller's variance review workspace. It consumes the
Block 4 API and **renders figures from the API; it computes none** (Constitution: Determinism
First at the presentation layer).

## Prerequisites

- Node 20+ and npm.
- For a live run: the Block 4 backend running (`uv run uvicorn api.main:app`), which needs
  `OPENROUTER_API_KEY` on the **backend** only — the frontend never sees it.

## Setup

```bash
npm install
```

## Generate the API types (from the FastAPI OpenAPI schema)

Types are generated, never hand-written, so the frontend can't drift from the Block 4 contract.

```bash
# 1) Dump the OpenAPI schema from the FastAPI app (no running server needed):
#    run from the repo root —
uv run python -c "import json; from api.main import app; json.dump(app.openapi(), open('web/src/api/openapi.json','w'), indent=2)"

# 2) Generate TypeScript types from it:
npm run gen:api        # openapi-typescript src/api/openapi.json -> src/api/types.ts
```

## Run

```bash
npm run dev            # Vite dev server; proxies /api -> http://localhost:8000 (the FastAPI backend)
```

Open the dev URL → the review workspace: P&L grid (left), variance queue (right), time-cut
selector, progress bar.

## Test (offline, deterministic)

```bash
npm test               # Vitest + React Testing Library + MSW — no backend, no network, no key
```

- `noArithmetic.test.ts` — the constitutional guard: the UI coerces/reformats no figure.
- `pnlGrid.test.tsx` — grid renders served display strings verbatim; markers.
- `VarianceCard.status.test.tsx` — controls per lifecycle status.
- `reviewFlow.test.tsx` — investigate / answer / accept / edit-then-accept / dismiss / 409 / investigate-all.
- `anchoring.test.tsx` — line ↔ card selection.
- `visual.test.tsx` — no monospace; tabular figures; semantic theme tokens.

## Architecture

- `src/api/` — generated `types.ts` + the thin typed `client.ts` (the only network access).
- `src/hooks/api.ts` — TanStack Query hooks; mutations invalidate → refetch so the UI mirrors the API.
- `src/components/` — `Workspace` (owns selection + time cut + anchoring), `PnlGrid`, `VarianceCard`
  (variant per status), `VarianceReviewPanel`, `TimeCutSelector`, `ProgressBar`, `ui/` primitives.
- `src/lib/format.ts` — DISPLAY-ONLY (never transforms a figure); `src/lib/anchor.ts` — line↔cards index.

## Constitution at the presentation layer

Every figure is the API's **display string** (formatted by deterministic Python in Block 4),
rendered character-for-character. The UI performs no ×100, rounding, or summing on a financial
value — enforced by `noArithmetic.test.ts`. Card status always mirrors the API's review state.
