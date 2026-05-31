"""US2 + US3: investigations (progressive status) and answer → draft, via TestClient + fake provider."""

from __future__ import annotations

from agent.fakes import FakeLLMProvider, final, tool_call

QUERY = tool_call("query_gl_detail", {"reporting_line": "it_costs", "period": 6, "scenario": "current_year"})
DRAFT = final({"status": "draft", "narrative": "EBITDA reached {{fig:flag.current_value}}.", "aggregates": []})
QUESTION = final({"status": "question", "hypothesis_text": "Late booking?",
                  "narrative": "EBITDA differs by {{fig:flag.abs_variance}}. Late booking?", "aggregates": []})
BAD = final({"status": "draft", "narrative": "EBITDA rose 5%.", "aggregates": []})  # raw digit → guard rejects

P6 = {"current_period": 6}  # the as-of month under test


def _ebitda_flag_id(client):
    flags = client.get("/variances", params=P6).json()
    return next(f["flag_id"] for f in flags
               if f["reporting_line"] == "it_costs" and f["time_cut"] == "ytd"
               and f["scenario_pair"] == "current_vs_prior_year")


def test_investigate_to_draft(make_api_client):
    client, _ = make_api_client(FakeLLMProvider([QUERY, DRAFT]))
    fid = _ebitda_flag_id(client)
    r = client.post(f"/review/{fid}/investigate", params=P6)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "drafted"
    assert body["original_draft"] is not None
    assert body["record"]["status"] == "draft"


def test_investigate_to_question(make_api_client):
    client, _ = make_api_client(FakeLLMProvider([QUERY, QUESTION]))
    fid = _ebitda_flag_id(client)
    body = client.post(f"/review/{fid}/investigate", params=P6).json()
    assert body["status"] == "awaiting_controller"
    assert body["record"]["question"] is not None


def test_answer_to_draft(make_api_client):
    client, _ = make_api_client(FakeLLMProvider([QUERY, QUESTION, DRAFT]))
    fid = _ebitda_flag_id(client)
    client.post(f"/review/{fid}/investigate", params=P6)  # → awaiting_controller
    r = client.post(f"/review/{fid}/answer", params=P6, json={"text": "Late-booked supplier invoice."})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "drafted"
    assert body["controller_answer"]["text"] == "Late-booked supplier invoice."
    assert body["original_draft"] is not None


def test_answer_on_non_awaiting_rejected(make_api_client):
    client, _ = make_api_client(FakeLLMProvider([QUERY, DRAFT]))
    fid = _ebitda_flag_id(client)
    client.post(f"/review/{fid}/investigate", params=P6)  # → drafted
    r = client.post(f"/review/{fid}/answer", params=P6, json={"text": "x"})
    assert r.status_code == 409


def test_failsafe_marks_failed_with_visible_reason(make_api_client):
    """A failed investigation is PERMANENT and visible — status 'failed' + an error reason,
    never silently back to 'detected', and no commentary."""
    client, _ = make_api_client(FakeLLMProvider([QUERY, BAD, BAD]))  # guard rejects twice
    fid = _ebitda_flag_id(client)
    body = client.post(f"/review/{fid}/investigate", params=P6).json()
    assert body["status"] == "failed"
    assert body["original_draft"] is None
    assert body["error"] and "guard rejected" in body["error"]
    # the failure is recorded in the action history (audit trail)
    history = client.get(f"/review/{fid}/history", params=P6).json()
    assert any(a["action"] == "investigate" and a["to_status"] == "failed" for a in history)


def test_failed_can_be_reinvestigated(make_api_client):
    client, _ = make_api_client(FakeLLMProvider([QUERY, BAD, BAD, QUERY, DRAFT]))
    fid = _ebitda_flag_id(client)
    assert client.post(f"/review/{fid}/investigate", params=P6).json()["status"] == "failed"
    # re-run from failed succeeds, clearing the error
    body = client.post(f"/review/{fid}/investigate", params=P6).json()
    assert body["status"] == "drafted"
    assert body["error"] is None


def test_reinvestigate_from_drafted_allowed(make_api_client):
    client, _ = make_api_client(FakeLLMProvider([QUERY, DRAFT, QUERY, DRAFT]))
    fid = _ebitda_flag_id(client)
    client.post(f"/review/{fid}/investigate", params=P6)          # → drafted
    r = client.post(f"/review/{fid}/investigate", params=P6)      # re-run from drafted → allowed
    assert r.status_code == 200 and r.json()["status"] == "drafted"


def test_reinvestigate_from_awaiting_rejected(make_api_client):
    client, _ = make_api_client(FakeLLMProvider([QUERY, QUESTION]))
    fid = _ebitda_flag_id(client)
    client.post(f"/review/{fid}/investigate", params=P6)          # → awaiting_controller
    r = client.post(f"/review/{fid}/investigate", params=P6)      # not allowed from awaiting_controller
    assert r.status_code == 409


def test_investigate_is_audited(make_api_client):
    client, _ = make_api_client(FakeLLMProvider([QUERY, DRAFT]))
    fid = _ebitda_flag_id(client)
    client.post(f"/review/{fid}/investigate", params=P6)
    history = client.get(f"/review/{fid}/history", params=P6).json()
    assert any(a["action"] == "investigate" and a["actor"] == "controller" and a["ts"]
               for a in history)


def test_unknown_flag_404(make_api_client):
    client, _ = make_api_client(FakeLLMProvider([]))
    assert client.post("/review/nope/investigate", params=P6).status_code == 404
    assert client.get("/review/nope", params=P6).status_code == 404
