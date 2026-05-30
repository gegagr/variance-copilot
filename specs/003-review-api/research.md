# Phase 0 Research: Review API Layer (Block 4)

The three clarify-session decisions (service core + thin HTTP/JSON adapter; edit-on-accepted
reverts to drafted; re-investigate only from detected/drafted) are encoded in the spec. This
research resolves *how* to realise them with FastAPI + SQLAlchemy/SQLite while keeping the
layer thin and the figures untouched.

---

## R1. Driving adapter over a thin application layer

**Decision**: FastAPI route handlers do three things only — validate the request (Pydantic),
call a method on `ReviewService`, and serialize the result. All orchestration and workflow live
in `api/services/review_service.py`, which depends only on the engine, the agent, and the
`ReviewStore` port — never on FastAPI. The state machine is a separate pure module
(`api/services/lifecycle.py`).

**Rationale**: Keeps the constitutional guarantees testable without a server (the service is
plain Python) and keeps routes trivial. Mirrors the hexagonal style already used in Block 3.

**Alternatives considered**: Logic in route handlers (couples workflow to HTTP, hard to unit
test); a framework-heavy service mesh (overkill for v0 local single-user).

## R2. Reusing Block 1/3 contract models in responses

**Decision**: Responses embed the existing Pydantic models directly — `FlaggedVariance`
(Block 1), `InvestigationRecord` / `Question` / `Draft` (Block 3) — wrapped in thin API DTOs
that add only review metadata (status, timestamps, ids). FastAPI serializes them; Decimals
remain strings (Pydantic v2 JSON default), so figures cross the wire exactly as the engine
produced them.

**Rationale**: "Reuse the contract models directly where possible" — avoids a second schema to
drift, and guarantees the API alters no figure (it never re-models a number).

**Alternatives considered**: Re-declaring API-specific figure models (drift risk + a place
arithmetic could sneak in — rejected).

## R3. The no-arithmetic (pass-through) guarantee

**Decision**: The service never constructs or mutates a numeric figure. P&L/flag/commentary
figures are taken from `PnLResult` / `FlaggedVariance` / `Draft` objects and serialized
unchanged. A test asserts every figure in an API response equals the engine's/agent's own
output for the same inputs (deep-equality on the contract models), and a lightweight check
confirms `api/services/` and `api/routes/` contain no arithmetic on figure fields.

**Rationale**: Determinism First (SC-001). The cheapest way to guarantee "alters no number" is
to never re-create one — pass the model through.

**Alternatives considered**: Re-serializing figures as floats for the frontend (violates exact
decimal — rejected; the frontend formats strings).

## R4. ReviewStore port + SQLite/SQLAlchemy adapter

**Decision**: A `ReviewStore` ABC (`data/review_store.py`) exposes get/upsert of a `ReviewItem`
and append/read of `ReviewAction` history. `SqliteReviewStore` (`data/sqlite_review_store.py`)
implements it with SQLAlchemy Core/ORM over a config-driven SQLite file. Tables: `review_item`
(flag_id PK, status, answer JSON, original_draft JSON, edited_text, dismissed flag, timestamps)
and `review_action` (id, flag_id, action, actor, ts, from_status, to_status, payload JSON).
Contract models are stored as JSON columns (they are immutable snapshots), not re-modelled into
relational figure columns.

**Rationale**: Mirrors the repository pattern (VI); SQLAlchemy makes the schema port to
Postgres/Supabase in Block 2 with no service change. Storing contract models as JSON keeps
figures verbatim and avoids an ORM-level place to alter them.

**Alternatives considered**: Plain JSON-file store (simpler but doesn't demonstrate the
DB-portable path the user asked for); a full relational decomposition of figures (reintroduces a
numeric surface — rejected).

## R5. The lifecycle state machine

**Decision**: `lifecycle.py` defines `ReviewStatus` and a transition table keyed by
`(status, action) → new_status`, with explicit allowed sets:
- `investigate`: {detected, drafted} → investigating (re-run discards prior draft).
- internal resolve of an investigation: investigating → awaiting_controller (Question) |
  drafted (Draft); a fail-safe (no grounded output) returns the item to `detected`.
- `answer`: awaiting_controller → drafted.
- `accept`: drafted → accepted.
- `edit`: drafted → drafted; accepted → drafted (re-accept required).
- `dismiss`: {detected, awaiting_controller, drafted, accepted} → dismissed.
Any `(status, action)` not in the table raises a `InvalidTransition` the adapter maps to HTTP
409. "Resolved" = {accepted, dismissed}.

**Rationale**: FR-008/FR-009 + the clarifications. A declarative table makes SC-005 (every
invalid transition rejected) a data-driven test.

**Alternatives considered**: Implicit status mutation scattered across service methods (untestable,
error-prone — rejected).

## R6. Synchronous per-variance investigation

**Decision**: `POST .../investigate` sets status to investigating, runs the Block 3
`investigate(...)` synchronously, persists the resulting `InvestigationRecord`, and sets status
to awaiting_controller or drafted (or back to detected on fail-safe). The response carries the
record. The per-variance status read supports progressive polling regardless.

**Rationale**: The spec's v0 execution model; simplest correct path. The status field keeps the
contract async-ready.

**Alternatives considered**: Background tasks / job queue (deferred — unneeded complexity for v0
local single-user).

## R7. Composition root & dependency injection

**Decision**: `api/main.py` builds the app and registers FastAPI dependency providers in
`api/deps.py`: `get_config`, `get_repository` (FixtureRepository), `get_gl_repository`
(GLDetailRepository), `get_agent_settings`, `get_provider` (OpenRouterProvider in prod), and
`get_review_store` (SqliteReviewStore). Tests use `app.dependency_overrides` to inject the
`FakeLLMProvider` and a temp-file/in-memory SQLite store — no network, deterministic.

**Rationale**: FastAPI-idiomatic composition; `dependency_overrides` is the clean seam for
offline tests.

**Alternatives considered**: Global singletons (hard to override in tests — rejected).

## R8. Auditability — review actions

**Decision**: Every state-changing service method appends a `ReviewAction`
(action, actor, ts, from_status, to_status, payload) via the store before/after the transition.
`actor` is the single configured controller id (`APISettings.controller_id`, default
"controller") in v0. Timestamps are taken at the adapter boundary and passed into the service so
the service stays deterministic in tests (caller-supplied `now`, as in Block 3's audit).

**Rationale**: FR-013/FR-014, Principle II. Caller-supplied time keeps service tests
deterministic.

**Alternatives considered**: Logging only to a file (not queryable per variance — rejected;
history must be retrievable, FR-014).

## R9. Editing preserves provenance

**Decision**: The `ReviewItem` keeps the original Block 3 `Draft` (immutable JSON snapshot) for
the life of the item. An edit writes `edited_text` (+ records a `ReviewAction`) and reverts
status to drafted; the original draft is never overwritten. `GET` of the item returns both.

**Rationale**: FR-012/SC-003 + the edit-revert clarification.

**Alternatives considered**: Overwriting the draft text with the edit (loses provenance —
rejected).

## R10. CORS, settings, and the SQLite file

**Decision**: `APISettings` (Pydantic) holds `sqlite_path` (default `build/review.db`,
git-ignored), `cors_origin` (default the local frontend, e.g. `http://localhost:5173`), and
`controller_id`. CORS is enabled for that origin via FastAPI middleware. The SQLite path is
config/env-driven; `build/` is already git-ignored.

**Rationale**: V (config-driven) + VIII (the review DB must not be committed).

**Alternatives considered**: Hardcoded origin/path (not config-driven — rejected).

## R11. Test strategy

**Decision**: `TestClient(app)` with `dependency_overrides` → `FakeLLMProvider` + a temp SQLite
file. Suites: pass-through/no-arithmetic, investigation+answer, review actions (accept/edit/
dismiss + edit-revert + provenance), a data-driven lifecycle matrix (valid succeed / invalid →
409), persistence-across-restart (close + re-open the store, assert state), progress + ordered
accepted set, and response-shape/contract.

**Rationale**: The user's testing list; all offline and deterministic.

**Alternatives considered**: Hitting a live server / real model (flaky, network — rejected).

---

## Resolved unknowns summary

| Topic | Resolution |
|-------|-----------|
| Layering | FastAPI driving adapter → `ReviewService` → engine/agent/`ReviewStore` ports |
| Response models | Reuse Block 1/3 contracts as JSON; thin DTOs add review metadata only |
| No-arithmetic | Pass models through; test asserts figure-equality with engine/agent output |
| Persistence | `ReviewStore` port + SQLAlchemy/SQLite adapter; contracts stored as JSON snapshots |
| State machine | Declarative `(status, action) → status` table; invalid → 409 |
| Investigation exec | Synchronous per variance; status keeps contract poll/async-ready |
| Composition | `api/main.py` + `deps.py`; tests via `dependency_overrides` |
| Audit | `ReviewAction` history per item; actor = config; caller-supplied timestamp |
| Provenance | Original Draft snapshot retained; edit writes `edited_text` + reverts to drafted |
| Settings | `APISettings`: sqlite path (git-ignored), CORS origin, controller id |
