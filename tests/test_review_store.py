"""Foundational: ReviewStore round-trip + persistence across a simulated restart (SC-008)."""

from __future__ import annotations

from data.review_store import (
    ReviewAction,
    ReviewActionType,
    ReviewItem,
    ReviewStatus,
)
from data.sqlite_review_store import SqliteReviewStore


def _item(flag_id="ebitda|ytd|current_vs_prior_year|value_default") -> ReviewItem:
    return ReviewItem(flag_id=flag_id, reporting_line="ebitda", status=ReviewStatus.DRAFTED,
                      edited_text="EBITDA outperformed.", created_at="t0", updated_at="t1")


def test_upsert_get_roundtrip(tmp_path):
    store = SqliteReviewStore(tmp_path / "r.db")
    item = _item()
    store.upsert(item)
    got = store.get(item.flag_id)
    assert got is not None
    assert got.status is ReviewStatus.DRAFTED
    assert got.edited_text == "EBITDA outperformed."


def test_upsert_updates_in_place(tmp_path):
    store = SqliteReviewStore(tmp_path / "r.db")
    item = _item()
    store.upsert(item)
    item.status = ReviewStatus.ACCEPTED
    store.upsert(item)
    assert store.get(item.flag_id).status is ReviewStatus.ACCEPTED
    assert len(store.list_all()) == 1


def test_action_history_order(tmp_path):
    store = SqliteReviewStore(tmp_path / "r.db")
    fid = "f1"
    for i, action in enumerate([ReviewActionType.INVESTIGATE, ReviewActionType.ACCEPT]):
        store.append_action(ReviewAction(
            action_id=f"a{i:03d}", flag_id=fid, action=action, actor="controller",
            ts="t", from_status=ReviewStatus.DETECTED, to_status=ReviewStatus.DRAFTED,
        ))
    acts = store.actions_for(fid)
    assert [a.action for a in acts] == [ReviewActionType.INVESTIGATE, ReviewActionType.ACCEPT]


def test_persistence_survives_restart(tmp_path):
    """Re-opening the store at the same path returns the same state (SC-008)."""
    path = tmp_path / "r.db"
    store = SqliteReviewStore(path)
    item = _item()
    store.upsert(item)
    store.append_action(ReviewAction(
        action_id="a000", flag_id=item.flag_id, action=ReviewActionType.ACCEPT, actor="controller",
        ts="t", from_status=ReviewStatus.DRAFTED, to_status=ReviewStatus.ACCEPTED,
    ))
    del store  # simulate process exit

    reopened = SqliteReviewStore(path)  # new process, same file
    got = reopened.get(item.flag_id)
    assert got is not None and got.edited_text == "EBITDA outperformed."
    assert len(reopened.actions_for(item.flag_id)) == 1
