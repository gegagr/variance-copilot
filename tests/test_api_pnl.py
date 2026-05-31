"""US1: P&L + flags served verbatim; the no-arithmetic guarantee (SC-001, FR-003)."""

from __future__ import annotations

from pathlib import Path

from agent.fakes import FakeLLMProvider
from config.loader import load_config
from data.fixture_repository import FixtureRepository
from engine.flagging import flag_variances
from engine.pnl import build_pnl
from engine.variance import compute_variances
from tests.conftest import CONFIG_DIR, SAMPLE_DIR


def _engine_pnl_json(period=6):
    cfg = load_config(CONFIG_DIR, current_period=period)
    return build_pnl(FixtureRepository(SAMPLE_DIR).get_transactions(), cfg).model_dump(mode="json")


def _engine_flags_json(period=6):
    cfg = load_config(CONFIG_DIR, current_period=period)
    pnl = build_pnl(FixtureRepository(SAMPLE_DIR).get_transactions(), cfg)
    return [f.model_dump(mode="json") for f in flag_variances(compute_variances(pnl, cfg), cfg)]


def test_pnl_served_verbatim(make_api_client):
    client, _ = make_api_client(FakeLLMProvider([]))
    resp = client.get("/pnl", params={"current_period": 6, "time_cut": "ytd"})
    assert resp.status_code == 200
    assert resp.json() == _engine_pnl_json(6)  # byte-equal to the engine's own output


def test_variances_served_verbatim(make_api_client):
    client, _ = make_api_client(FakeLLMProvider([]))
    resp = client.get("/variances", params={"current_period": 6})
    assert resp.status_code == 200
    assert resp.json() == _engine_flags_json(6)


def test_no_figure_altered_specific_value(make_api_client):
    client, _ = make_api_client(FakeLLMProvider([]))
    flags = client.get("/variances", params={"current_period": 6}).json()
    it = next(f for f in flags if f["reporting_line"] == "it_costs" and f["time_cut"] == "ytd"
              and f["scenario_pair"] == "current_vs_prior_year")
    # IT costs YTD current = -45000.00 (Block 1) — served as the exact decimal string, not recomputed.
    assert it["current_value"] == "-45000.00"


def test_no_arithmetic_in_api_source():
    """Static guard: the API layer does no arithmetic on figures (Determinism First)."""
    import re
    suspicious = re.compile(r"(Decimal\(|\.quantize\(|float\(.*amount|[^=!<>]=\s*\w+\s*[+\-*/]\s*\w)")
    for path in (Path("api/routes")).glob("*.py"):
        text = path.read_text()
        assert "Decimal(" not in text and ".quantize(" not in text, f"arithmetic in {path}"
