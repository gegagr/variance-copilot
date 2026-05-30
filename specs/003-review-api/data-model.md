# Phase 1 Data Model: Review API Layer (Block 4)

Review-state models live in `data/review_store.py` (domain) and are persisted by
`data/sqlite_review_store.py` (SQLAlchemy). API request/response DTOs live in `api/schemas.py`
and **reuse** the Block 1/3 contract models verbatim — the API never re-models a figure.

## Enumerations

```python
class ReviewStatus(str, Enum):
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    AWAITING_CONTROLLER = "awaiting_controller"
    DRAFTED = "drafted"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"

RESOLVED = {ReviewStatus.ACCEPTED, ReviewStatus.DISMISSED}

# Canonical identifier is `awaiting_controller` (underscore). The hyphenated
# "awaiting-controller" appears only in prose; the enum value is authoritative.

class ReviewActionType(str, Enum):
    INVESTIGATE = "investigate"
    ANSWER = "answer"
    ACCEPT = "accept"
    EDIT = "edit"
    DISMISS = "dismiss"
```

## Reused contract models (NOT re-declared)

- **FlaggedVariance** (Block 1) — the flag; the review item's identity is its `flag_id`.
- **InvestigationRecord / Question / Draft** (Block 3) — stored as immutable JSON snapshots.
- **PnLResult** (Block 1) — served for the P&L endpoint, verbatim.

## Domain models (`data/review_store.py`)

### ReviewItem

| Field | Type | Notes |
|-------|------|-------|
| `flag_id` | `str` | Primary key; equals the Block 1 `FlaggedVariance.flag_id`. |
| `reporting_line` | `str` | For layout-ordered output (from the flag). |
| `status` | `ReviewStatus` | Current lifecycle state (always exactly one). |
| `record` | `InvestigationRecord \| None` | Latest Block 3 record (JSON snapshot). |
| `original_draft` | `Draft \| None` | The AI draft as first produced — never overwritten. |
| `controller_answer` | `ControllerInput \| None` | The controller's verbatim answer (Block 3 type). |
| `edited_text` | `str \| None` | The controller's edited commentary (original retained separately). |
| `created_at` | `str` | ISO timestamp. |
| `updated_at` | `str` | ISO timestamp of last transition. |

Invariant: `original_draft` holds the AI draft of the CURRENT investigation run — it is set
when a Draft first appears in a run and is immutable *within* that run. Re-investigating a
`drafted` item starts a fresh run: it resets `original_draft` to the new run's AI draft and
clears `edited_text`. Within a run, `edited_text` is the only mutable commentary field.

### ReviewAction (audit entry)

| Field | Type | Notes |
|-------|------|-------|
| `action_id` | `str` | Sequential / unique. |
| `flag_id` | `str` | The item acted on. |
| `action` | `ReviewActionType` | investigate / answer / accept / edit / dismiss. |
| `actor` | `str` | Single controller id in v0 (config). |
| `ts` | `str` | ISO timestamp (caller-supplied → deterministic in tests). |
| `from_status` | `ReviewStatus` | Status before. |
| `to_status` | `ReviewStatus` | Status after. |
| `payload` | `dict \| None` | e.g. the answer text or edited text. |

## Persistence (`data/sqlite_review_store.py`)

SQLAlchemy tables (SQLite v0; portable to Postgres/Supabase):

- `review_item(flag_id PK, reporting_line, status, record_json, original_draft_json,
  controller_answer_json, edited_text, created_at, updated_at)`
- `review_action(action_id PK, flag_id, action, actor, ts, from_status, to_status, payload_json)`

Contract models are stored as JSON (`*_json`) — immutable snapshots; no figure is decomposed
into numeric columns (so the store cannot alter a figure).

## ReviewStore port (`data/review_store.py`)

```python
class ReviewStore(ABC):
    @abstractmethod
    def get(self, flag_id: str) -> ReviewItem | None: ...
    @abstractmethod
    def upsert(self, item: ReviewItem) -> None: ...
    @abstractmethod
    def list_all(self) -> list[ReviewItem]: ...
    @abstractmethod
    def append_action(self, action: ReviewAction) -> None: ...
    @abstractmethod
    def actions_for(self, flag_id: str) -> list[ReviewAction]: ...
```

## API DTOs (`api/schemas.py`)

Thin wrappers that add review metadata around reused contracts:

- **ReviewItemView** — `flag_id`, `status`, `variance: FlaggedVariance`,
  `record: InvestigationRecord | None`, `original_draft: Draft | None`, `edited_text: str | None`,
  `controller_answer: ControllerInput | None`, `updated_at`.
- **AnswerRequest** — `text: str`, `accepted_hypothesis: bool = True`.
- **EditRequest** — `edited_text: str`.
- **ReviewProgressView** — `total: int`, `resolved: int`, `by_status: dict[str, int]`.
- **AcceptedCommentaryItem** — `flag_id`, `reporting_line`, `order: int`, `text: str`,
  `is_edited: bool`, `provenance: DraftProvenance`. Emitted in P&L-layout order.
- **PnLView** / **FlagsView** — `PnLResult` / `list[FlaggedVariance]` passed through verbatim.

`text` in AcceptedCommentaryItem is the accepted commentary (edited text if edited, else the
draft commentary) — both originate from Block 3; the API copies, never recomputes.

## Service surface (`api/services/review_service.py`)

```python
class ReviewService:
    def __init__(self, repo, gl_repo, config, agent_settings, provider, store): ...
    def get_pnl(self, current_period, time_cut) -> PnLResult: ...          # pass-through
    def get_flags(self, current_period) -> list[FlaggedVariance]: ...      # pass-through
    def investigate(self, flag_id, *, now) -> ReviewItem: ...             # detected/drafted → investigating → ...
    def answer(self, flag_id, answer, *, now) -> ReviewItem: ...          # awaiting_controller → drafted
    def accept(self, flag_id, *, now) -> ReviewItem: ...                  # drafted → accepted
    def edit(self, flag_id, edited_text, *, now) -> ReviewItem: ...       # drafted|accepted → drafted
    def dismiss(self, flag_id, *, now) -> ReviewItem: ...                 # → dismissed
    def progress(self) -> ReviewProgressView: ...
    def accepted_commentary(self) -> list[AcceptedCommentaryItem]: ...    # P&L-layout order
```

The service applies `lifecycle.transition(status, action)` (raising `InvalidTransition`),
persists via the store, and appends a `ReviewAction` for every state change. It holds **no
financial computation** — figures come from the engine/agent objects unchanged.

## Validation & invariants (enforced by tests)

- **No-arithmetic / pass-through**: every figure in any API response equals the engine's/agent's
  own output for the same inputs (SC-001).
- **Lifecycle**: every valid `(status, action)` succeeds; every invalid one is rejected with the
  status unchanged → HTTP 409 (SC-005).
- **Final only on accept**: a commentary is "final" iff status == accepted (SC-002); editing an
  accepted item reverts to drafted.
- **Provenance**: `original_draft` retained alongside `edited_text` after an edit (SC-003).
- **Audit**: every state change appends a `ReviewAction` with actor + ts (SC-004).
- **Progress**: resolved == accepted + dismissed over total flagged (SC-006).
- **Ordering**: accepted commentary returned in P&L-layout order, dismissed excluded (SC-007).
- **Persistence**: state identical after closing and re-opening the store (SC-008).
