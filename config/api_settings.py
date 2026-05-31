"""API settings — config/env-driven, never hardcoded (Constitution Principle V)."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel


class APISettings(BaseModel):
    sqlite_path: Path = Path("build/review.db")   # git-ignored
    audit_path: Path = Path("build/agent_audit.jsonl")  # LLM interaction audit log (git-ignored)
    cors_origin: str = "http://localhost:5173"     # local frontend
    controller_id: str = "controller"              # single-user actor (v0)
    current_period: int = 6                         # the review session's fiscal period


def load_api_settings() -> APISettings:
    return APISettings(
        sqlite_path=Path(os.environ.get("REVIEW_DB_PATH", "build/review.db")),
        audit_path=Path(os.environ.get("AGENT_AUDIT_PATH", "build/agent_audit.jsonl")),
        cors_origin=os.environ.get("CORS_ORIGIN", "http://localhost:5173"),
        controller_id=os.environ.get("CONTROLLER_ID", "controller"),
        current_period=int(os.environ.get("CURRENT_PERIOD", "6")),
    )
