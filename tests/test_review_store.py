"""Foundational: ReviewStore round-trip, persistence, and per-(current_period, flag_id) keying.

The store is keyed by the as-of month AND the flag id, so each period owns an independent review
queue and lifecycle state (FR-005/FR-006). Tests cover both adapters and the SQLite recreate-on-
schema-mismatch path (research R3).
"""

from __future__ import annotations

from sqlalchemy import Column, MetaData, String, Table, create_engine

from data.review_store import (
    InMemoryReviewStore,
    ReviewAction,
    ReviewActionType,
    ReviewItem,
    ReviewStatus,
)
from data.sqlite_review_store import SqliteReviewStore


def _item(flag_id="ebitda|ytd|current_vs_prior_year|value_default", *, current_period=6,
          status=ReviewStatus.DRAFTED) -> ReviewItem:
    return ReviewItem(flag_id=flag_id, current_period=current_period, reporting_line="ebitda",
                      status=status, edited_text="EBITDA outperformed.", created_at="t0", updated_at="t1")


# --------------------------------------------------------------------------- #
# SQLite round-trip + persistence (existing coverage, now period-aware).
# --------------------------------------------------------------------------- #
def test_upsert_get_roundtrip(tmp_path):
    store = SqliteReviewStore(tmp_path / "r.db")
    item = _item()
    store.upsert(item)
    got = store.get(item.current_period, item.flag_id)
    assert got is not None
    assert got.status is ReviewStatus.DRAFTED
    assert got.edited_text == "EBITDA outperformed."


def test_upsert_updates_in_place(tmp_path):
    store = SqliteReviewStore(tmp_path / "r.db")
    item = _item()
    store.upsert(item)
    item.status = ReviewStatus.ACCEPTED
    store.upsert(item)
    assert store.get(item.current_period, item.flag_id).status is ReviewStatus.ACCEPTED
    assert len(store.list_all(item.current_period)) == 1


def test_action_history_order(tmp_path):
    store = SqliteReviewStore(tmp_path / "r.db")
    fid = "f1"
    for i, action in enumerate([ReviewActionType.INVESTIGATE, ReviewActionType.ACCEPT]):
        store.append_action(ReviewAction(
            action_id=f"a{i:03d}", flag_id=fid, current_period=6, action=action, actor="controller",
            ts="t", from_status=ReviewStatus.DETECTED, to_status=ReviewStatus.DRAFTED,
        ))
    acts = store.actions_for(6, fid)
    assert [a.action for a in acts] == [ReviewActionType.INVESTIGATE, ReviewActionType.ACCEPT]


def test_persistence_survives_restart(tmp_path):
    """Re-opening the store at the same path returns the same state."""
    path = tmp_path / "r.db"
    store = SqliteReviewStore(path)
    item = _item()
    store.upsert(item)
    store.append_action(ReviewAction(
        action_id="a000", flag_id=item.flag_id, current_period=6, action=ReviewActionType.ACCEPT,
        actor="controller", ts="t", from_status=ReviewStatus.DRAFTED, to_status=ReviewStatus.ACCEPTED,
    ))
    del store  # simulate process exit

    reopened = SqliteReviewStore(path)  # new process, same file
    got = reopened.get(item.current_period, item.flag_id)
    assert got is not None and got.edited_text == "EBITDA outperformed."
    assert len(reopened.actions_for(item.current_period, item.flag_id)) == 1


# --------------------------------------------------------------------------- #
# T002 — per-(current_period, flag_id) keying (in-memory).
# --------------------------------------------------------------------------- #
def test_in_memory_keys_by_period_and_flag():
    store = InMemoryReviewStore()
    store.upsert(_item(flag_id="f1", current_period=6))
    assert store.get(6, "f1") is not None
    assert store.get(5, "f1") is None  # same flag, different period -> independent


def test_in_memory_list_all_is_period_scoped():
    store = InMemoryReviewStore()
    store.upsert(_item(flag_id="f1", current_period=6))
    store.upsert(_item(flag_id="f2", current_period=6))
    store.upsert(_item(flag_id="f1", current_period=5))
    assert {i.flag_id for i in store.list_all(6)} == {"f1", "f2"}
    assert {i.flag_id for i in store.list_all(5)} == {"f1"}


def test_in_memory_same_flag_two_periods_are_independent():
    store = InMemoryReviewStore()
    store.upsert(_item(flag_id="f1", current_period=6, status=ReviewStatus.ACCEPTED))
    store.upsert(_item(flag_id="f1", current_period=5, status=ReviewStatus.DETECTED))
    assert store.get(6, "f1").status is ReviewStatus.ACCEPTED
    assert store.get(5, "f1").status is ReviewStatus.DETECTED


def test_in_memory_actions_scoped_by_period_and_flag():
    store = InMemoryReviewStore()
    for p in (5, 6):
        store.append_action(ReviewAction(
            action_id=f"a-{p}", flag_id="f1", current_period=p, action=ReviewActionType.INVESTIGATE,
            actor="controller", ts="t", from_status=ReviewStatus.DETECTED,
            to_status=ReviewStatus.INVESTIGATING,
        ))
    assert [a.action_id for a in store.actions_for(6, "f1")] == ["a-6"]
    assert [a.action_id for a in store.actions_for(5, "f1")] == ["a-5"]


# --------------------------------------------------------------------------- #
# T003 — SQLite composite-key isolation + recreate-on-schema-mismatch.
# --------------------------------------------------------------------------- #
def test_sqlite_composite_key_isolation(tmp_path):
    store = SqliteReviewStore(tmp_path / "r.db")
    store.upsert(_item(flag_id="f1", current_period=6, status=ReviewStatus.ACCEPTED))
    store.upsert(_item(flag_id="f1", current_period=5, status=ReviewStatus.DETECTED))
    assert store.get(6, "f1").status is ReviewStatus.ACCEPTED
    assert store.get(5, "f1").status is ReviewStatus.DETECTED
    assert {i.flag_id for i in store.list_all(6)} == {"f1"}


def test_sqlite_recreates_old_schema_db(tmp_path):
    """An existing DB whose review_item lacks current_period is dropped + recreated, then works."""
    path = tmp_path / "r.db"
    # Pre-create an OLD-schema review_item table (no current_period column).
    md = MetaData()
    Table("review_item", md,
          Column("flag_id", String, primary_key=True),
          Column("reporting_line", String),
          Column("status", String))
    engine = create_engine(f"sqlite:///{path}")
    md.create_all(engine)
    engine.dispose()

    store = SqliteReviewStore(path)  # must detect the mismatch and recreate
    item = _item(flag_id="f1", current_period=6)
    store.upsert(item)
    assert store.get(6, "f1") is not None
    assert store.get(5, "f1") is None
