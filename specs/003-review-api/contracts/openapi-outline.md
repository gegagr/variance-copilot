# Contract: API surface (the UI contract)

The thin HTTP/JSON adapter over `ReviewService`. FastAPI publishes the live OpenAPI/Swagger at
`/docs` and `/openapi.json`; this outline is the human-readable summary the UI block builds
against. All figures are passed through from the engine/agent verbatim (Decimals serialized as
strings); the API computes none.

Base: local single-user, no auth. CORS enabled for the configured frontend origin.

## Read endpoints (idempotent; never mutate review state)

| Method & path | Purpose | Response |
|---------------|---------|----------|
| `GET /pnl?current_period={1-12}&time_cut={...}` | The engine P&L for the period/time cut | `PnLResult` (verbatim) |
| `GET /variances?current_period={1-12}` | Flagged variances for the period | `list[FlaggedVariance]` (verbatim) |
| `GET /review` | All review items + their statuses | `list[ReviewItemView]` |
| `GET /review/{flag_id}` | One review item (incl. record, original draft, edit) | `ReviewItemView` or `404` |
| `GET /review/{flag_id}/history` | The audit trail for the item | `list[ReviewAction]` |
| `GET /review/progress` | Resolved-vs-total progress | `ReviewProgressView` |
| `GET /review/accepted` | Accepted commentary in P&L-layout order | `list[AcceptedCommentaryItem]` |

`time_cut` ∈ `prior_month_ytd | current_month | ytd | full_year`.

## State-changing endpoints (each appends a ReviewAction; lifecycle-enforced)

| Method & path | Action | Body | Success | Rejects |
|---------------|--------|------|---------|---------|
| `POST /review/{flag_id}/investigate` | run/re-run investigation | – | `200 ReviewItemView` (status investigating→awaiting_controller \| drafted; or detected on fail-safe) | `409` if not from detected/drafted; `404` unknown flag |
| `POST /review/{flag_id}/answer` | answer the question | `AnswerRequest` | `200 ReviewItemView` (drafted, with Draft) | `409` if not awaiting_controller |
| `POST /review/{flag_id}/accept` | accept the draft | – | `200 ReviewItemView` (accepted) | `409` if not drafted |
| `POST /review/{flag_id}/edit` | edit the commentary | `EditRequest` | `200 ReviewItemView` (drafted; original retained) | `409` if not drafted/accepted |
| `POST /review/{flag_id}/dismiss` | dismiss the variance | – | `200 ReviewItemView` (dismissed) | `409` if already resolved/investigating |

### Error model

- `404 Not Found` — unknown period or `flag_id` (never a partial/invented response).
- `409 Conflict` — invalid lifecycle transition; body names the current status and the rejected
  action; **status is left unchanged**.
- `422 Unprocessable Entity` — request body fails Pydantic validation.
- `502/failed` — when the agent fail-safes (no grounded output): the item stays `detected` and the
  response signals the failure; **no commentary is ever returned**.

## Request/response models

Reuse the Block 1/3 contracts directly (`FlaggedVariance`, `InvestigationRecord`, `Question`,
`Draft`, `ControllerInput`, `DraftProvenance`) plus the thin DTOs in `api/schemas.py`
(`ReviewItemView`, `AnswerRequest`, `EditRequest`, `ReviewProgressView`,
`AcceptedCommentaryItem`). See data-model.md.

## Guarantees encoded in the surface

- No endpoint returns a figure the API computed — only engine/agent output (SC-001).
- No endpoint returns commentary as final unless `status == accepted` (SC-002, SC-010).
- Every state-changing endpoint records an actor + timestamp (SC-004).
- Contract tests assert response shapes match these documented models / the published OpenAPI.
