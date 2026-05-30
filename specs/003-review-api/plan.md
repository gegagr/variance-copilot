# Implementation Plan: Review API Layer (Block 4)

**Branch**: `003-review-api` | **Date**: 2026-05-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-review-api/spec.md`

## Summary

Block 4 is the API and review-state layer: the composition root that wires the fixture
Repository, the engine (Block 1), and the agent (Block 3), and exposes them to a client. It
serves the P&L, the flagged variances, and the AI investigation records, and it manages the
controller's review workflow (run investigation → answer → accept / edit / dismiss).

Technical approach: **driving adapter over a thin application layer (hexagonal)**. A pure
Python **service layer** orchestrates engine + agent + a `ReviewStore`, holding the workflow
state machine; a thin **FastAPI** driving adapter validates input, calls the service, and
serializes results — no financial or workflow logic in route handlers. Review state persists
in **SQLite via SQLAlchemy** behind a `ReviewStore` port (so it ports cleanly to
Supabase/Postgres later). The layer recomputes nothing — engine/agent figures pass through
verbatim (an arithmetic-free guarantee, tested). Nothing is final until status is `accepted`;
editing an accepted item reverts it to `drafted` (re-accept required) and retains both texts.
Every state-changing action is logged with actor + timestamp. All tests run offline with the
Block 3 `FakeLLMProvider` and FastAPI's `TestClient`.

## Technical Context

**Language/Version**: Python 3.12+, `uv` (same project as Blocks 1 & 3).

**Primary Dependencies**: FastAPI (+ OpenAPI/Swagger at `/docs`), Pydantic v2 (reusing
`FlaggedVariance`, `InvestigationRecord`, `Question`, `Draft` contract models), SQLAlchemy +
SQLite (review-state persistence), `httpx`/`starlette` TestClient (tests). Reuses Block 1
(`engine/`, `config/`, `data/`) and Block 3 (`agent/`) unchanged.

**Storage**: SQLite file for review state (config-driven path, git-ignored). Mock GL/config
fixtures from Blocks 1 & 3. No real connectors.

**Testing**: pytest + FastAPI `TestClient`; the agent runs on Block 3's `FakeLLMProvider` →
fully offline and deterministic. State-machine, persistence-across-restart, pass-through
(no-arithmetic), and contract tests.

**Target Platform**: Local single-user HTTP service (v0). CORS enabled for the local frontend.

**Project Type**: Web service (driving adapter) over the existing Python project.

**Performance Goals**: Not latency-bound; v0 runs investigations synchronously per variance.

**Constraints**: No financial computation in this layer (Determinism First — pass-through only).
Never bypass Block 3's traceability guard (all commentary comes from the agent). Nothing final
without an explicit accept. Every state change audited. Single-user, no auth.

**Scale/Scope**: One review item per flagged variance; six lifecycle states; ~8 endpoints; one
SQLite store behind a port.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | How this plan complies | Status |
|---|-----------|------------------------|--------|
| I | Determinism First | The API performs NO arithmetic; engine/agent figures pass through verbatim. A test asserts served figures equal the engine's own output (no recompute/round). Workflow logic (the state machine) is not financial logic. | ✅ PASS |
| II | Auditability | Every state-changing action (answer, accept, edit, dismiss, investigate) is persisted with action, actor, timestamp, and before/after status; action history is retrievable. | ✅ PASS |
| III | LLM Scope | The API triggers the Block 3 agent but never expands its authority and never generates commentary itself — all commentary (and its traceability guard) comes from Block 3. | ✅ PASS |
| IV | Human in the Loop | Commentary is final only when status is `accepted`; everything else is a proposal. Editing an accepted item reverts to `drafted` (re-accept required). Invalid transitions are rejected. | ✅ PASS |
| V | Config-Driven | P&L structure still comes from Block 1 config; the SQLite path, CORS origin, and agent settings are config/env, not hardcoded. | ✅ PASS |
| VI | Source-Agnostic Data | GL/transaction data flows through the Block 1 `Repository`; the API depends on the abstraction (fixture impl in v0). The `ReviewStore` is itself a port with a SQLite adapter. | ✅ PASS |
| VII | Excel & Word Export First-Class | N/A here (report assembly is out of scope), but the accepted-commentary endpoint emits in P&L-layout order, ready for the report layer. | ✅ N/A |
| VIII | No Real Client Data | Fixture repository + mock config only; the SQLite review-state file is git-ignored; no real connectors. | ✅ PASS |

**Result**: PASS. No violations — Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/003-review-api/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── openapi-outline.md       # endpoints, request/response shapes (the UI contract)
│   ├── review_store.md          # ReviewStore port contract
│   └── lifecycle.md             # the review state machine (transitions + rejections)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root — additions to the Blocks 1 & 3 project)

```text
api/                             # Block 4: FastAPI driving adapter + application layer
├── __init__.py
├── main.py                      # FastAPI app + composition root (wires deps); CORS; /docs
├── deps.py                      # FastAPI dependency providers (config, repo, engine, agent, store)
├── schemas.py                   # request/response models (reuse Block 1/3 contracts; add API DTOs)
├── routes/
│   ├── __init__.py
│   ├── pnl.py                   # GET P&L / flagged variances (pass-through)
│   ├── investigations.py        # trigger/get investigation; submit answer
│   └── review.py                # accept / edit / dismiss; progress; accepted commentary
└── services/
    ├── __init__.py
    ├── review_service.py        # application layer: orchestrates engine+agent+store; the workflow
    └── lifecycle.py             # explicit state machine (valid transitions, rejections)

data/                            # additions
├── review_store.py              # ReviewStore PORT (ABC) + ReviewItem persistence model
└── sqlite_review_store.py       # SQLAlchemy/SQLite adapter implementing ReviewStore

config/                          # additions
└── api_settings.py              # APISettings (sqlite path, CORS origin, controller actor id)

tests/
├── test_api_pnl.py              # P&L + flags pass-through; no-arithmetic guarantee
├── test_api_investigations.py   # trigger/get investigation; answer → draft (fake provider)
├── test_api_review_actions.py   # accept / edit / dismiss; edit-revert; provenance retained
├── test_lifecycle.py            # state machine: every valid transition ok, every invalid rejected
├── test_review_store.py         # persistence survives a simulated restart (re-open the store)
├── test_api_progress.py         # progress count; accepted commentary in P&L-layout order
└── test_api_contract.py         # response shapes match documented schemas / OpenAPI
```

**Structure Decision**: A FastAPI **driving adapter** (`api/routes/`) sits over a pure
**application/service layer** (`api/services/`). Route handlers only validate, delegate, and
serialize. `review_service.py` is the workflow brain — it composes the Block 3 agent loop,
applies the `lifecycle.py` state machine, and persists through the `ReviewStore` port; it
contains **no financial computation** (figures come from Block 1/Block 3 verbatim). The
`ReviewStore` port (`data/review_store.py`) has a SQLite/SQLAlchemy adapter
(`data/sqlite_review_store.py`), mirroring the repository pattern so Block 2 can swap in
Postgres/Supabase. The FastAPI app (`api/main.py`) is the composition root, injecting the
fixture `Repository`, engine, agent (+ `LLMProvider`), and `ReviewStore` via FastAPI
dependencies — tests override the provider with Block 3's `FakeLLMProvider`. Dependency
direction: `routes → services → (engine, agent, ReviewStore ports)`; the service never imports
FastAPI.

## Complexity Tracking

> No constitution violations. No entries required.
