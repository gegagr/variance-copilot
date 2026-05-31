# Contract — period-aware ReviewStore port + adapters

The `ReviewStore` port gains a `current_period` dimension. Both adapters (SQLite, in-memory)
implement the same period-aware signature, so `ReviewService` still depends only on the abstraction
(Principle VI). Contract models stay immutable JSON snapshots — the store never decomposes a figure.

## Port (abstract)

```python
class ReviewStore(ABC):
    def get(self, current_period: int, flag_id: str) -> Optional[ReviewItem]: ...
    def upsert(self, item: ReviewItem) -> None: ...                 # item.current_period is authoritative
    def list_all(self, current_period: int) -> list[ReviewItem]: ...
    def append_action(self, action: ReviewAction) -> None: ...      # action.current_period is authoritative
    def actions_for(self, current_period: int, flag_id: str) -> list[ReviewAction]: ...
```

- `ReviewItem` and `ReviewAction` each gain a `current_period: int` field (see data-model.md).
- Identity of an item is `(current_period, flag_id)`.

## InMemoryReviewStore (test double)

- Items in a `dict[tuple[int, str], ReviewItem]` keyed by `(current_period, flag_id)`.
- `get` / `upsert` use the tuple key; `list_all(p)` returns items whose `current_period == p`.
- Actions stored in a list; `actions_for(p, flag_id)` filters by both, preserving insertion order.
- Returns deep copies (unchanged behavior) so callers can't mutate stored state.

## SqliteReviewStore (durable adapter)

**Schema**:
- `review_item`: add `current_period INTEGER NOT NULL`; **primary key = (`current_period`, `flag_id`)**.
- `review_action`: add `current_period INTEGER NOT NULL` (action_id remains the PK).
- Upsert: `sqlite_insert(...).on_conflict_do_update(index_elements=["current_period", "flag_id"], …)`.
- Reads filter on `current_period` (and `flag_id` where applicable); `actions_for` orders by
  `action_id`.

**Recreate-on-mismatch (migration note)**:
- The primary key changed, so a pre-existing `build/review.db` from the old single-key schema is
  incompatible.
- On construction, inspect the existing `review_item` table; if it exists but lacks the
  `current_period` column, **drop and recreate** the review tables, then `create_all`.
- Safe because the DB is dev-only, git-ignored, and holds mock review state (Principle VIII). This
  also clears stale rows (old flag_ids from before the data rebuild) that contributed to the
  empty/desynced queue.
- A fresh DB (no `review_item` table) just runs `create_all` as today.

## Invariants (testable)
- `upsert` then `get(p, flag)` round-trips an item under its period; `get(p', flag)` returns `None`.
- `list_all(p)` returns exactly the items for period `p`.
- The same `flag_id` under two periods yields two independent items with independent statuses.
- After recreate-on-mismatch, the store reads/writes cleanly with the composite key (a test seeds an
  old-schema table and asserts the adapter recreates and works).
