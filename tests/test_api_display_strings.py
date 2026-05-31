"""Block 5 dependency: /pnl/view and /variances/view carry Python display strings; raw endpoints unchanged."""

from __future__ import annotations

from decimal import Decimal

from agent.fakes import FakeLLMProvider
from engine import format as fmt


def test_variances_view_has_display_strings(make_api_client):
    client, _ = make_api_client(FakeLLMProvider([]))
    items = client.get("/variances/view", params={"current_period": 6}).json()
    assert items
    eb = next(f for f in items if f["reporting_line"] == "it_costs" and f["time_cut"] == "ytd"
              and f["scenario_pair"] == "current_vs_prior_year")
    # display strings equal format.* of the raw values
    assert eb["current_display"] == fmt.money(Decimal(eb["current_value"]))
    assert eb["comparator_display"] == fmt.money(Decimal(eb["comparator_value"]))
    assert eb["abs_display"] == fmt.money(Decimal(eb["abs_variance"]))
    assert eb["pct_display"] == fmt.percent(Decimal(eb["pct_variance"]))
    # it_costs YTD current = -€45,000.00 (months 1-5 @ -6k + month 6 @ -15k)
    assert eb["current_display"] == "€-45,000.00"


def test_no_subtotal_or_margin_rows_are_flagged(make_api_client):
    """Only detail lines are flagged, so the served view never contains a subtotal/margin row."""
    client, _ = make_api_client(FakeLLMProvider([]))
    items = client.get("/variances/view", params={"current_period": 6}).json()
    assert items
    assert all(f["line_type"] in ("revenue", "cost") for f in items)


def test_pnl_view_cells_have_display(make_api_client):
    client, _ = make_api_client(FakeLLMProvider([]))
    view = client.get("/pnl/view", params={"current_period": 6, "time_cut": "ytd"}).json()
    revenue = next(l for l in view["lines"] if l["reporting_line"] == "external_revenue")
    for cell in revenue["cells"]:
        assert cell["display"].startswith("€")
    margin = next(l for l in view["lines"] if l["line_type"] == "margin")
    assert all(c["display"].endswith("%") or c["display"] == "n/m" for c in margin["cells"])


def test_raw_endpoints_unchanged(make_api_client):
    """The byte-pure /pnl and /variances must NOT have gained display fields."""
    client, _ = make_api_client(FakeLLMProvider([]))
    flag = client.get("/variances", params={"current_period": 6}).json()[0]
    assert "current_display" not in flag  # raw endpoint stays verbatim
