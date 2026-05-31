"""US4: accept / edit / dismiss — lifecycle, provenance, audit (FR-010/011/012, SC-002/003/004)."""

from __future__ import annotations

from agent.fakes import FakeLLMProvider, final, tool_call

QUERY = tool_call("query_gl_detail", {"reporting_line": "it_costs", "period": 6, "scenario": "current_year"})
DRAFT = final({"status": "draft", "narrative": "EBITDA reached {{fig:flag.current_value}}.", "aggregates": []})

P6 = {"current_period": 6}  # the as-of month under test


def _to_drafted(make_api_client, extra=()):
    provider = FakeLLMProvider([QUERY, DRAFT, *extra])
    client, store = make_api_client(provider)
    flags = client.get("/variances", params=P6).json()
    fid = next(f["flag_id"] for f in flags if f["reporting_line"] == "it_costs" and f["time_cut"] == "ytd"
               and f["scenario_pair"] == "current_vs_prior_year")
    client.post(f"/review/{fid}/investigate", params=P6)  # → drafted
    return client, fid


def test_accept_makes_final(make_api_client):
    client, fid = _to_drafted(make_api_client)
    body = client.post(f"/review/{fid}/accept", params=P6).json()
    assert body["status"] == "accepted"


def test_accept_requires_draft(make_api_client):
    client, _ = make_api_client(FakeLLMProvider([]))
    flags = client.get("/variances", params=P6).json()  # seeds detected items
    fid = flags[0]["flag_id"]
    assert client.post(f"/review/{fid}/accept", params=P6).status_code == 409  # still detected


def test_edit_retains_original_and_records(make_api_client):
    client, fid = _to_drafted(make_api_client)
    body = client.post(f"/review/{fid}/edit", params=P6, json={"edited_text": "Controller wording."}).json()
    assert body["status"] == "drafted"
    assert body["edited_text"] == "Controller wording."
    assert body["original_draft"] is not None  # original AI draft retained (provenance)
    history = client.get(f"/review/{fid}/history", params=P6).json()
    assert any(a["action"] == "edit" for a in history)


def test_edit_on_accepted_reverts_to_drafted(make_api_client):
    client, fid = _to_drafted(make_api_client)
    client.post(f"/review/{fid}/accept", params=P6)  # → accepted
    body = client.post(f"/review/{fid}/edit", params=P6, json={"edited_text": "Tweak."}).json()
    assert body["status"] == "drafted"  # must be re-accepted
    assert body["original_draft"] is not None


def test_dismiss(make_api_client):
    client, fid = _to_drafted(make_api_client)
    body = client.post(f"/review/{fid}/dismiss", params=P6).json()
    assert body["status"] == "dismissed"


def test_every_action_audited(make_api_client):
    client, fid = _to_drafted(make_api_client)
    client.post(f"/review/{fid}/accept", params=P6)
    history = client.get(f"/review/{fid}/history", params=P6).json()
    actions = {a["action"] for a in history}
    assert {"investigate", "accept"} <= actions
    assert all(a["actor"] == "controller" and a["ts"] for a in history)
