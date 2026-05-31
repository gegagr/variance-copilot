"""005 As-of period: one current_period flows through every endpoint; per-period review state.

Covers the headline bug (empty/desynced queue) and per-month isolation. Offline: FakeLLMProvider
+ InMemoryReviewStore via the make_api_client fixture.
"""

from __future__ import annotations

from agent.fakes import FakeLLMProvider, final, tool_call

P6 = {"current_period": 6}
P5 = {"current_period": 5}

QUERY = tool_call("query_gl_detail", {"reporting_line": "it_costs", "period": 6, "scenario": "current_year"})
DRAFT = final({"status": "draft", "narrative": "Driven to {{fig:flag.current_value}}.", "aggregates": []})


def _it_costs_ytd_flag(client, params):
    flags = client.get("/variances", params=params).json()
    return next(f["flag_id"] for f in flags
                if f["reporting_line"] == "it_costs" and f["time_cut"] == "ytd"
                and f["scenario_pair"] == "current_vs_prior_year")


# --------------------------------------------------------------------------- #
# US1 — every read view agrees for one as-of month.
# --------------------------------------------------------------------------- #
def test_flag_set_is_consistent_across_endpoints(make_api_client):
    """For current_period=6, /variances, /review, and /review/progress report the SAME flags."""
    client, _ = make_api_client(FakeLLMProvider([]))
    variance_ids = {f["flag_id"] for f in client.get("/variances", params=P6).json()}
    review_ids = {it["flag_id"] for it in client.get("/review", params=P6).json()}
    progress = client.get("/review/progress", params=P6).json()

    assert variance_ids == review_ids
    assert progress["total"] == len(variance_ids)


def test_review_queue_non_empty_with_full_flag_set_at_period_6(make_api_client):
    """The queue holds one item per flagged variance for the as-of month — the FULL flag set
    (all time cuts + scenario pairs, matching /variances), not only current_month rows —
    and every item starts 'detected'."""
    client, _ = make_api_client(FakeLLMProvider([]))
    variances = client.get("/variances", params=P6).json()
    items = client.get("/review", params=P6).json()

    assert items, "the review queue must not be empty given the embedded anomalies"
    assert {it["flag_id"] for it in items} == {f["flag_id"] for f in variances}
    assert all(it["status"] == "detected" for it in items)


# --------------------------------------------------------------------------- #
# US3 — per-month isolation + idempotent seeding.
# --------------------------------------------------------------------------- #
def test_switching_period_preserves_prior_month_state(make_api_client):
    """Acting in period 6 then visiting period 5 leaves period 6's work intact; period 5 is
    seeded fresh (all detected), so one month's decisions never leak into another."""
    client, _ = make_api_client(FakeLLMProvider([QUERY, DRAFT]))
    fid6 = _it_costs_ytd_flag(client, P6)
    client.post(f"/review/{fid6}/investigate", params=P6)  # → drafted
    assert client.post(f"/review/{fid6}/accept", params=P6).json()["status"] == "accepted"

    # First visit to period 5 seeds it independently — nothing accepted there.
    p5_items = client.get("/review", params=P5).json()
    assert p5_items and all(it["status"] == "detected" for it in p5_items)

    # Returning to period 6, the accepted item is exactly as left.
    p6_after = {it["flag_id"]: it for it in client.get("/review", params=P6).json()}
    assert p6_after[fid6]["status"] == "accepted"


def test_seeding_is_idempotent_and_never_resets_state(make_api_client):
    """Repeated /review for a period yields the same items/statuses; an accepted item is not
    reset by a later seed pass."""
    client, _ = make_api_client(FakeLLMProvider([QUERY, DRAFT]))

    first = client.get("/review", params=P6).json()
    second = client.get("/review", params=P6).json()
    assert len(first) == len(second)
    assert {it["flag_id"]: it["status"] for it in first} == {it["flag_id"]: it["status"] for it in second}

    fid = _it_costs_ytd_flag(client, P6)
    client.post(f"/review/{fid}/investigate", params=P6)
    client.post(f"/review/{fid}/accept", params=P6)
    # A later seed pass (GET /review) must NOT revert the accepted item to detected.
    after = {it["flag_id"]: it["status"] for it in client.get("/review", params=P6).json()}
    assert after[fid] == "accepted"
