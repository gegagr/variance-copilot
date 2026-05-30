"""Architecture guard: the agent CORE has no SDK/HTTP calls; only the adapter touches httpx/key."""

from __future__ import annotations

from tests.conftest import ROOT

AGENT_DIR = ROOT / "agent"
CORE_FILES = ["investigate.py", "commentary.py", "guards.py", "models.py", "tools.py", "audit.py", "fakes.py"]
FORBIDDEN = ("import httpx", "OPENROUTER_API_KEY", "openai", "anthropic", "requests.")


def test_core_has_no_sdk_or_key_access():
    offenders = []
    for name in CORE_FILES:
        text = (AGENT_DIR / name).read_text(encoding="utf-8")
        for needle in FORBIDDEN:
            if needle in text:
                offenders.append(f"{name}: {needle!r}")
    assert not offenders, f"agent core purity violations: {offenders}"


def test_only_provider_adapter_imports_httpx():
    provider = (AGENT_DIR / "provider.py").read_text(encoding="utf-8")
    assert "httpx" in provider and "OPENROUTER_API_KEY" in provider  # the adapter is here, as intended
