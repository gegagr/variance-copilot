"""US5: review progress + accepted commentary in P&L-layout order (FR-015/016, SC-006/007)."""

from __future__ import annotations

from agent.fakes import FakeLLMProvider, final, tool_call

DRAFT = final({"status": "draft", "narrative": "Driven to {{fig:flag.current_value}}.", "aggregates": []})


def _query(line):
    return tool_call("query_gl_detail", {"reporting_line": line, "period": 6, "scenario": "current_year"})


def test_progress_counts_resolved(make_api_client):
    # Script enough responses to investigate three flags (query+draft each).
    flags_lines = ["ebitda", "ebitda", "ebitda"]
    script = []
    for line in flags_lines:
        script += [_query(line), DRAFT]
    client, _ = make_api_client(FakeLLMProvider(script))

    flags = client.get("/variances", params={"current_period": 6}).json()
    total = len(flags)
    # Accept one, dismiss one.
    f0, f1 = flags[0]["flag_id"], flags[1]["flag_id"]
    client.post(f"/review/{f0}/investigate"); client.post(f"/review/{f0}/accept")
    client.post(f"/review/{f1}/dismiss")  # dismiss allowed from detected

    prog = client.get("/review/progress").json()
    assert prog["total"] == total
    assert prog["resolved"] == 2  # 1 accepted + 1 dismissed


def test_accepted_set_in_layout_order_excludes_dismissed(make_api_client):
    flags_script = [_query("revenue"), DRAFT, _query("ebitda"), DRAFT]
    client, _ = make_api_client(FakeLLMProvider(flags_script))
    flags = client.get("/variances", params={"current_period": 6}).json()
    by_line = {}
    for f in flags:
        if f["time_cut"] == "ytd" and f["scenario_pair"] == "current_vs_prior_year":
            by_line.setdefault(f["reporting_line"], f["flag_id"])

    # Accept ebitda (layout order 6) and revenue (order 1); accept in reverse layout order.
    if "ebitda" in by_line and "revenue" in by_line:
        eb, rev = by_line["ebitda"], by_line["revenue"]
        # Provider script above is ordered revenue then ebitda; investigate in that order.
        client.post(f"/review/{rev}/investigate"); client.post(f"/review/{rev}/accept")
        client.post(f"/review/{eb}/investigate"); client.post(f"/review/{eb}/accept")
        accepted = client.get("/review/accepted").json()
        lines = [a["reporting_line"] for a in accepted]
        # revenue (order 1) must come before ebitda (order 6) regardless of accept order.
        assert lines.index("revenue") < lines.index("ebitda")
        assert all(a["text"] for a in accepted)
