# Quickstart: Review API Layer (Block 4)

Block 4 adds a FastAPI driving adapter over a thin `ReviewService`, persisting review state in
SQLite behind a `ReviewStore` port. The service is plain Python (testable offline); the whole
test suite runs with the Block 3 `FakeLLMProvider` and FastAPI's `TestClient` — no network.

## Prerequisites

- Blocks 1 & 3 working (`uv sync`).
- For a *live* run (real model), an OpenRouter key; tests need none.

## Run the API (live)

```bash
uv sync
export OPENROUTER_API_KEY=sk-...        # live only; never committed/logged
uv run uvicorn api.main:app --reload
# Swagger UI: http://localhost:8000/docs
```

The app is the composition root: it wires the fixture `Repository`, the engine, the agent
(+ `OpenRouterProvider`), and `SqliteReviewStore` (path from `APISettings`, git-ignored).

## A typical review flow (HTTP)

```text
GET  /pnl?current_period=6&time_cut=ytd        # engine P&L (verbatim figures)
GET  /variances?current_period=6               # Block 1 flags
POST /review/{flag_id}/investigate             # runs the agent → question or draft
POST /review/{flag_id}/answer  {"text": "..."} # answer a question → draft
POST /review/{flag_id}/edit    {"edited_text": "..."}   # optional; reverts to drafted
POST /review/{flag_id}/accept                  # makes the commentary final
GET  /review/progress                          # resolved / total
GET  /review/accepted                          # accepted commentary in P&L-layout order
```

## Use the service directly (offline, fake provider)

```python
from agent.fakes import FakeLLMProvider, tool_call, final
from api.services.review_service import ReviewService
from data.review_store import ReviewItem  # or an in-memory store for tests

svc = ReviewService(repo, gl_repo, config, agent_settings,
                    provider=FakeLLMProvider([...]), store=in_memory_store)
item = svc.investigate(flag_id, now="2026-05-31T00:00:00Z")
assert item.status in ("awaiting_controller", "drafted")
```

No FastAPI, no network — the workflow is pure Python.

## Tests

```bash
uv run pytest tests/test_lifecycle.py          # the state machine (valid succeed / invalid 409)
uv run pytest tests/test_api_pnl.py            # pass-through; the no-arithmetic guarantee
uv run pytest tests/test_review_store.py       # state survives a simulated restart
uv run pytest                                   # everything, offline
```

`TestClient` tests override the provider with `FakeLLMProvider` and point the store at a temp
SQLite file via `app.dependency_overrides`.

## Guarantees (by construction + tests)

- **No financial logic**: the API returns engine/agent objects verbatim; a test asserts every
  served figure equals the engine's/agent's own output.
- **Proposal until accepted**: nothing is final unless `status == accepted`; editing an accepted
  item reverts to `drafted` (re-accept required), retaining the original AI draft.
- **Audited**: every answer/accept/edit/dismiss/investigate records actor + timestamp.
- **Never bypasses the guard**: all commentary comes from Block 3; the API generates none.

## Config & safety

- `APISettings`: SQLite path (default `build/review.db`, git-ignored), CORS origin, controller id.
- Mock data only; the review DB and any real inputs stay out of version control.
