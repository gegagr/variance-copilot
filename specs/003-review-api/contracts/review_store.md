# Contract: ReviewStore port

Review state lives behind this port (Principle VI — same pattern as the data `Repository`).
Block 4 ships one adapter, `SqliteReviewStore`; Block 2 can add Postgres/Supabase behind the
same signature with no service change.

## Port

```python
# data/review_store.py
from abc import ABC, abstractmethod

class ReviewStore(ABC):
    @abstractmethod
    def get(self, flag_id: str) -> "ReviewItem | None": ...

    @abstractmethod
    def upsert(self, item: "ReviewItem") -> None: ...

    @abstractmethod
    def list_all(self) -> list["ReviewItem"]: ...

    @abstractmethod
    def append_action(self, action: "ReviewAction") -> None: ...

    @abstractmethod
    def actions_for(self, flag_id: str) -> list["ReviewAction"]: ...
```

### Guarantees the service relies on

- **Durability**: writes persist across process restarts (SC-008). Re-opening a store at the
  same path returns the same items and action history.
- **Snapshot fidelity**: contract models (`InvestigationRecord`, `Draft`, `ControllerInput`) are
  stored and returned byte-equivalent (JSON) — no figure is altered or re-typed.
- **Append-only history**: `append_action` never mutates prior actions; `actions_for` returns
  them in insertion order.

## SqliteReviewStore (Block 4 adapter)

```python
# data/sqlite_review_store.py
class SqliteReviewStore(ReviewStore):
    def __init__(self, sqlite_path: Path): ...   # creates tables if absent
```

- SQLAlchemy over a config-driven SQLite file (git-ignored).
- Tables: `review_item`, `review_action` (see data-model.md). Contract models in JSON columns.

## Contract tests

- upsert + get round-trips a `ReviewItem` (incl. embedded contract snapshots) unchanged.
- closing and re-opening the store at the same path preserves all items + actions (restart).
- `append_action`/`actions_for` preserve order; `list_all` returns every item.
- a test double `InMemoryReviewStore` satisfies the same port (proves the service depends on the
  abstraction, not SQLite).
