# Quickstart — As-of Period Selector

How to run and verify the feature + bug fix. All checks are offline and deterministic.

## Prerequisites
- Python deps via `uv` (backend); Node deps via `npm` in `web/`.
- **One-time**: delete any stale review DB so the new composite key takes effect:
  `rm -f build/review.db` (the adapter also auto-recreates an incompatible DB; this is belt-and-suspenders).

## Backend — verify the bug fix and per-period isolation

Run the suite (extends the existing API/service/store tests):

```bash
uv run pytest -q
```

Expected new/updated assertions:
- **Consistent flag set**: for `current_period=6`, the flags from `/variances`, `/review`, and
  `/review/progress` are the same set.
- **Queue non-empty @ P6**: `GET /review?current_period=6` returns one item per flagged variance
  (the embedded anomalies → non-empty).
- **Per-period isolation**: accept/dismiss items under period 6, seed period 5, return to period 6 —
  period 6 statuses unchanged; the same `flag_id` under period 5 is independent.
- **Idempotent seeding**: calling `GET /review?current_period=6` repeatedly yields the same item
  count and statuses.
- **Store re-key**: `upsert`/`get` round-trip per `(current_period, flag_id)`; old-schema DB is
  recreated on construction.

Manual smoke (optional), with the app running:

```bash
# same period everywhere -> agreeing flag sets, non-empty queue
curl 'localhost:8000/variances?current_period=6' | jq 'length'
curl 'localhost:8000/review?current_period=6'    | jq 'length'      # equal, non-zero
curl 'localhost:8000/review/progress?current_period=6' | jq '.total'

# a different month has its own queue/state
curl 'localhost:8000/review?current_period=5' | jq 'length'
```

## Frontend — verify the selector and refetch

```bash
cd web && npm test       # Vitest + RTL + MSW, offline
```

Expected:
- The **As of** selector renders the months with actuals and defaults to the latest (P6).
- Changing it refetches the grid, variances, and review queue for the new month (query keys include
  `current_period`).
- The **time-cut** selector still slices relative to the chosen as-of month (independent controls).
- The no-arithmetic guard still passes.

Dev run:

```bash
# terminal 1: backend
uv run uvicorn api.main:app --reload
# terminal 2: web (proxies /api -> backend)
cd web && npm run dev
```

Then: pick **As of = Jun (P6)** → the grid shows flagged lines and the review queue is non-empty and
matches them. Switch to **P5**, act on its flags, switch back to **P6** → P6's work is exactly as left.

## Guardrails
- Block 1 numbers are untouched — every existing engine/reconciliation/figure test stays green.
- `current_period` is an explicit input at every layer; never the wall clock.
- The OpenRouter key stays backend-only; the suite never calls the live API/LLM.
