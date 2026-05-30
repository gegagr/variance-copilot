"""JSON-lines audit log of every LLM interaction (Constitution Principle II).

Each call appends one entry: prompt/request, response, model id, and a caller-supplied
timestamp (passed in, not read from the clock, so tests are deterministic). The API key is
NEVER written — entries are redacted defensively before serialization.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

_REDACT_KEYS = {"authorization", "api_key", "openrouter_api_key", "bearer"}


def _redact(obj):
    if isinstance(obj, dict):
        return {
            k: ("***redacted***" if k.lower() in _REDACT_KEYS else _redact(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact(v) for v in obj]
    return obj


class AuditLog:
    """In-memory + optional JSON-lines file audit log."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else None
        self.entries: list[dict] = []

    def record(self, *, model: str, request: dict, response: dict, now: str,
               tool_calls: Optional[list] = None) -> str:
        entry_id = f"log-{len(self.entries) + 1:04d}"
        entry = {
            "entry_id": entry_id,
            "ts": now,
            "model": model,
            "request": _redact(request),
            "response": _redact(response),
            "tool_calls": _redact(tool_calls or []),
        }
        self.entries.append(entry)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        return entry_id
