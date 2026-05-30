"""Imperative composition root: load config -> repo -> pure core -> outputs.

This is the only place that wires I/O to the pure engine. Run with:

    uv run python -m shell.pipeline --config-dir config --sample-dir sample \
        --current-period 6 --out build/pnl.xlsx
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from config.loader import load_config
from data.fixture_repository import FixtureRepository
from engine.flagging import flag_variances
from engine.models import FlaggedVariance, PnLResult
from engine.pnl import build_pnl
from engine.variance import compute_variances
from export.excel import write_pnl


def run(config_dir: Path, sample_dir: Path, current_period: int | None, out: Path) -> dict:
    config = load_config(config_dir, current_period=current_period)
    repository = FixtureRepository(sample_dir)
    transactions = repository.get_transactions()

    result: PnLResult = build_pnl(transactions, config)
    variances = compute_variances(result, config)
    flags: list[FlaggedVariance] = flag_variances(variances, config)

    write_pnl(result, out)
    flags_path = Path(out).with_name("flags.json")
    flags_path.write_text(
        json.dumps([f.model_dump(mode="json") for f in flags], indent=2),
        encoding="utf-8",
    )

    return {
        "xlsx": str(out),
        "flags_json": str(flags_path),
        "flag_count": len(flags),
        "reconciled": result.reconciliation.is_complete,
        "residual": str(result.reconciliation.residual),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Variance Copilot deterministic engine (Block 1)")
    parser.add_argument("--config-dir", type=Path, default=Path("config"))
    parser.add_argument("--sample-dir", type=Path, default=Path("sample"))
    parser.add_argument("--current-period", type=int, default=None)
    parser.add_argument("--out", type=Path, default=Path("build/pnl.xlsx"))
    args = parser.parse_args()

    summary = run(args.config_dir, args.sample_dir, args.current_period, args.out)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
