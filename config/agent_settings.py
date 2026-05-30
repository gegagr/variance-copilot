"""Agent settings — config-driven, never hardcoded (Constitution Principle V)."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel


class AgentSettings(BaseModel):
    model_id: str
    temperature: Decimal = Decimal("0")
    max_tool_calls_per_variance: int = 4
    dominant_share_threshold: Decimal = Decimal("0.60")
    max_guard_retries: int = 1


def load_agent_settings(config_dir: Path) -> AgentSettings:
    path = Path(config_dir) / "agent_settings.csv"
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError("agent_settings.csv is empty")
    r = {k.strip(): (v or "").strip() for k, v in rows[0].items()}
    return AgentSettings(
        model_id=r["model_id"],
        temperature=Decimal(r.get("temperature", "0")),
        max_tool_calls_per_variance=int(r.get("max_tool_calls_per_variance", "4")),
        dominant_share_threshold=Decimal(r.get("dominant_share_threshold", "0.60")),
        max_guard_retries=int(r.get("max_guard_retries", "1")),
    )
