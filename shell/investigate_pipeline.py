"""Imperative composition root for Block 3 (live runs).

Runs Block 1 to produce flags + context, then investigates each flag with the real
OpenRouter provider behind the same port the tests drive with a fake. Writes one
InvestigationRecord per flag to JSON lines, plus the LLM audit log.

    uv run python -m shell.investigate_pipeline --current-period 6 --out build/investigations.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from config.agent_settings import load_agent_settings
from config.loader import load_config
from data.fixture_repository import FixtureRepository
from data.gl_detail_repository import GLDetailRepository
from engine.flagging import flag_variances
from engine.pnl import build_pnl
from engine.variance import compute_variances
from agent.audit import AuditLog
from agent.investigate import investigate
from agent.provider import OpenRouterProvider
from agent.tools import make_gl_tool


def run(config_dir: Path, sample_dir: Path, current_period: int | None, out: Path, *, now: str) -> dict:
    config = load_config(config_dir, current_period=current_period)
    settings = load_agent_settings(config_dir)

    transactions = FixtureRepository(sample_dir).get_transactions()
    pnl = build_pnl(transactions, config)
    flags = flag_variances(compute_variances(pnl, config), config)

    provider = OpenRouterProvider()
    gl_tool = make_gl_tool(GLDetailRepository(sample_dir), config)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    audit = AuditLog(path=out.with_name("audit.jsonl"))

    records = []
    for flag in flags:
        record = investigate(flag, pnl, provider=provider, gl_tool=gl_tool,
                             settings=settings, audit=audit, now=now)
        if record is not None:
            records.append(record)

    with out.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r.model_dump(mode="json")) + "\n")

    return {
        "flags": len(flags),
        "records": len(records),
        "investigations": str(out),
        "audit": str(audit.path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Variance Copilot AI investigation layer (Block 3)")
    parser.add_argument("--config-dir", type=Path, default=Path("config"))
    parser.add_argument("--sample-dir", type=Path, default=Path("sample"))
    parser.add_argument("--current-period", type=int, default=None)
    parser.add_argument("--out", type=Path, default=Path("build/investigations.jsonl"))
    parser.add_argument("--now", type=str, default="1970-01-01T00:00:00Z",
                        help="Timestamp stamped into the audit log (kept explicit for reproducibility).")
    args = parser.parse_args()
    summary = run(args.config_dir, args.sample_dir, args.current_period, args.out, now=args.now)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
