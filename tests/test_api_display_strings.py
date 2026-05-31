"""Block 5 dependency: /pnl/view and /variances/view carry Python display strings; raw endpoints unchanged."""

from __future__ import annotations

from decimal import Decimal

from agent.fakes import FakeLLMProvider
from engine import format as fmt


def test_variances_view_has_display_strings(make_api_client):
    client, _ = make_api_client(FakeLLMProvider([]))
    items = client.get("/variances/view", params={"current_period": 6}).json()
    assert items
    eb = next(f for f in items if f["reporting_line"] == "ebitda" and f["time_cut"] == "ytd"
              and f["scenario_pair"] == "current_vs_prior_year")
    # display strings equal format.* of the raw values
    assert eb["current_display"] == fmt.money(Decimal(eb["current_value"]))
    assert eb["comparator_display"] == fmt.money(Decimal(eb["comparator_value"]))
    assert eb["abs_display"] == fmt.money(Decimal(eb["abs_variance"]))
    assert eb["pct_display"] == fmt.percent(Decimal(eb["pct_variance"]))
    assert eb["current_display"] == "€78,600.00"  # known EBITDA YTD figure


def test_margin_view_uses_percent_and_points(make_api_client):
    client, _ = make_api_client(FakeLLMProvider([]))
    items = client.get("/variances/view", params={"current_period": 6}).json()
    margins = [f for f in items if f["line_type"] == "margin"]
    if margins:  # margin lines flag on pp
        m = margins[0]
        assert m["pp_display"] is not None and m["pp_display"].endswith(" pp")
        assert m["current_display"].endswith("%")
        assert m["abs_display"] is None and m["pct_display"] is None


def test_pnl_view_cells_have_display(make_api_client):
    client, _ = make_api_client(FakeLLMProvider([]))
    view = client.get("/pnl/view", params={"current_period": 6, "time_cut": "ytd"}).json()
    revenue = next(l for l in view["lines"] if l["reporting_line"] == "revenue")
    for cell in revenue["cells"]:
        assert cell["display"].startswith("€")
    margin = next(l for l in view["lines"] if l["line_type"] == "margin")
    assert all(c["display"].endswith("%") or c["display"] == "n/m" for c in margin["cells"])


def test_raw_endpoints_unchanged(make_api_client):
    """The byte-pure /pnl and /variances must NOT have gained display fields."""
    client, _ = make_api_client(FakeLLMProvider([]))
    flag = client.get("/variances", params={"current_period": 6}).json()[0]
    assert "current_display" not in flag  # raw endpoint stays verbatim
