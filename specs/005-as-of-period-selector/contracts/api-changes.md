# Contract — API changes: `current_period` everywhere (no recompute)

The API gains **one parameter** on the review routes so every endpoint reads the *same* as-of month
the caller selected. No response *shape* changes (the existing DTOs are unchanged); the API still
computes no figure — engine objects pass through verbatim.

## Read endpoints

| Endpoint | Today | After |
|----------|-------|-------|
| `GET /pnl` | `current_period` (query), `time_cut` | unchanged |
| `GET /pnl/view` | `current_period`, `time_cut` | unchanged |
| `GET /variances` | `current_period` | unchanged |
| `GET /variances/view` | `current_period` | unchanged |
| `GET /review` | *(none — uses `settings.current_period`)* | **`current_period` (query, `ge=1,le=12`)** |
| `GET /review/progress` | *(none — uses `settings.current_period`)* | **`current_period` (query, `ge=1,le=12`)** |
| `GET /review/accepted` | *(none)* | **`current_period` (query)** — accepted commentary for that month |
| `GET /review/{flag_id}` | *(none)* | **`current_period` (query)** — the item for that month |
| `GET /review/{flag_id}/history` | *(none)* | **`current_period` (query)** — actions for that month's item |

- `GET /review` seeds that month's flags idempotently (detected) then returns
  `list[ReviewItemView]` for `current_period`.
- `GET /review/progress` returns `ReviewProgressView` counted **within** `current_period`
  (resolved-of-total for that month only).

## Mutation endpoints

Each mutation must target the correct per-period item, so it takes `current_period` (query param,
`ge=1, le=12`):

| Endpoint | After |
|----------|-------|
| `POST /review/{flag_id}/investigate` | + `current_period` (query) |
| `POST /review/{flag_id}/answer` | + `current_period` (query); body `AnswerRequest` unchanged |
| `POST /review/{flag_id}/accept` | + `current_period` (query) |
| `POST /review/{flag_id}/edit` | + `current_period` (query); body `EditRequest` unchanged |
| `POST /review/{flag_id}/dismiss` | + `current_period` (query) |

- Each returns the updated `ReviewItemView` for `(current_period, flag_id)`.
- Lifecycle errors stay `409` (`InvalidTransition`); unknown `(period, flag)` stays `404`
  (`NotFound`).

## Service contract (workflow brain)

`ReviewService` loses its implicit `_session_period`; every period-dependent method takes
`current_period` explicitly:

```
get_pnl(current_period, time_cut)              -> PnLResult
get_pnl_view(current_period, time_cut)         -> PnLResultView
get_flags(current_period)                      -> list[FlaggedVariance]   # seeds that period idempotently
get_flags_view(current_period)                 -> list[FlaggedVarianceView]
investigate(flag_id, current_period, now)      -> ReviewItem
answer(flag_id, current_period, text, accepted_hypothesis, now) -> ReviewItem
accept(flag_id, current_period, now)           -> ReviewItem
edit(flag_id, current_period, edited_text, now)-> ReviewItem
dismiss(flag_id, current_period, now)          -> ReviewItem
progress(current_period)                        -> ReviewProgressView
accepted_commentary(current_period)             -> list[AcceptedCommentaryItem]
history(flag_id, current_period)                -> list[ReviewAction]
```

- The service builds the P&L/flags for the requested `current_period` (via the engine and the
  existing `load_config(current_period=…)`), looks up or seeds the `(current_period, flag_id)` item,
  applies the lifecycle transition, persists, and appends a period-scoped `ReviewAction`.
- It **constructs no figure**: P&L, flags, and commentary come from engine/agent objects verbatim.

## Invariants (testable)
- For a fixed `current_period`, the flag set returned by `/variances`, `/review`, and
  `/review/progress` is identical.
- `GET /review?current_period=6` is **non-empty** given the embedded anomalies.
- Acting on `(6, flag)` leaves `(5, flag)` untouched, and vice-versa.
- Repeated `GET /review?current_period=p` never duplicates items or changes statuses.
- No endpoint falls back to a configured default period when the caller supplies one.
