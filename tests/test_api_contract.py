"""Contract: response shapes match the documented schemas; the error model behaves (FR-018/020)."""

from __future__ import annotations

from agent.fakes import FakeLLMProvider
from agent.models import InvestigationRecord
from engine.models import FlaggedVariance, PnLResult


def test_pnl_and_variances_shapes(make_api_client):
    client, _ = make_api_client(FakeLLMProvider([]))
    PnLResult.model_validate(client.get("/pnl", params={"current_period": 6, "time_cut": "ytd"}).json())
    for f in client.get("/variances", params={"current_period": 6}).json():
        FlaggedVariance.model_validate(f)


def test_review_item_view_shape(make_api_client):
    client, _ = make_api_client(FakeLLMProvider([]))
    client.get("/variances", params={"current_period": 6})  # seed items
    items = client.get("/review", params={"current_period": 6}).json()
    assert items
    for it in items:
        assert {"flag_id", "reporting_line", "status"} <= set(it)
        assert it["status"] in {
            "detected", "investigating", "awaiting_controller", "drafted", "accepted", "dismissed"
        }


def test_record_validates_against_block3_contract(make_api_client):
    from agent.fakes import final, tool_call
    provider = FakeLLMProvider([
        tool_call("query_gl_detail", {"reporting_line": "it_costs", "period": 6, "scenario": "current_year"}),
        final({"status": "draft", "narrative": "EBITDA at {{fig:flag.current_value}}.", "aggregates": []}),
    ])
    client, _ = make_api_client(provider)
    fid = next(f["flag_id"] for f in client.get("/variances", params={"current_period": 6}).json()
               if f["reporting_line"] == "it_costs" and f["time_cut"] == "ytd")
    body = client.post(f"/review/{fid}/investigate", params={"current_period": 6}).json()
    InvestigationRecord.model_validate(body["record"])  # served record is the Block 3 contract


def test_error_model(make_api_client):
    client, _ = make_api_client(FakeLLMProvider([]))
    assert client.get("/review/does-not-exist", params={"current_period": 6}).status_code == 404  # not found
    assert client.get("/pnl", params={"current_period": 99}).status_code == 422  # validation
    # 409 invalid transition: accept a freshly-detected item
    fid = client.get("/variances", params={"current_period": 6}).json()[0]["flag_id"]
    assert client.post(f"/review/{fid}/accept", params={"current_period": 6}).status_code == 409


def test_openapi_published(make_api_client):
    client, _ = make_api_client(FakeLLMProvider([]))
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]
    for p in ("/pnl", "/variances", "/review/progress", "/review/accepted",
              "/review/{flag_id}/investigate", "/review/{flag_id}/answer",
              "/review/{flag_id}/accept", "/review/{flag_id}/edit", "/review/{flag_id}/dismiss"):
        assert p in paths, f"missing documented path {p}"
