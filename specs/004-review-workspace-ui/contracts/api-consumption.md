# Contract: Block 4 API consumption (the UI's only data source)

The UI talks to Block 4 exclusively, through a thin typed client whose types are **generated** from
the FastAPI `/openapi.json`. No other network access exists.

## Endpoints consumed

| UI need | Endpoint | Notes |
|---------|----------|-------|
| P&L grid for a cut | `GET /pnl/view?current_period&time_cut` | `PnLResult` w/ `PnlCellView` display strings |
| Flagged variances | `GET /variances/view?current_period` | `FlaggedVarianceView[]` (incl. `*_display`) |
| Review items + statuses | `GET /review` | `ReviewItemView[]` |
| One review item | `GET /review/{flag_id}` | status, record, draft, edit |
| Progress | `GET /review/progress` | `{ total, resolved, by_status }` |
| Accepted commentary | `GET /review/accepted` | layout-ordered, for context |
| Trigger investigation | `POST /review/{flag_id}/investigate` | sync; returns updated item |
| Submit answer | `POST /review/{flag_id}/answer` | `AnswerRequest` → drafted item |
| Accept | `POST /review/{flag_id}/accept` | → accepted |
| Edit | `POST /review/{flag_id}/edit` | `EditRequest` → drafted (re-accept) |
| Dismiss | `POST /review/{flag_id}/dismiss` | → dismissed |

The UI consumes the `/view` endpoints (display strings). The raw `GET /pnl` and `GET /variances`
remain byte-pure and unchanged (their Block 4 verbatim pass-through tests are untouched); they are
available for the future report layer.

## Type generation flow

1. Run the Block 4 backend; fetch `/openapi.json`.
2. Generate `web/src/api/types.ts` (e.g. `openapi-typescript`). Committed but regenerable; never
   hand-edited.
3. `api/client.ts` wraps `fetch` with those types — the single network seam.

## Error & status mapping (UI behavior)

- `200` → update the relevant query; cards reflect the returned status.
- `409` (invalid transition) → the UI shows the API's current status (no stale optimistic state);
  the offered controls already gate on status so this is a safety net.
- `404` → not-found surfaced without crashing.
- `422` → request validation error surfaced near the input (e.g. empty answer prevented client-side
  first).
- Investigation fail-safe (item returns to `detected` with no draft) → card shows an error/failed
  treatment; no commentary shown.

## Rules

- All network access goes through `api/client.ts`; components never call `fetch` directly.
- Mutations invalidate `review`/`progress` queries → refetch → UI mirrors API state.
- The OpenRouter key is never present in the frontend; the UI never calls the model.
