"""Determinism / snapshot tests (Constitution Principle I; FR-025, SC-001)."""

from __future__ import annotations

import json

from engine.flagging import flag_variances
from engine.pnl import build_pnl
from engine.variance import compute_variances


def _serialize(transactions, cfg) -> str:
    result = build_pnl(transactions, cfg)
    variances = compute_variances(result, cfg)
    flags = flag_variances(variances, cfg)
    return json.dumps(
        {
            "pnl": result.model_dump(mode="json"),
            "flags": [f.model_dump(mode="json") for f in flags],
        },
        sort_keys=True,
    )


def test_identical_inputs_produce_identical_output(transactions, cfg6):
    first = _serialize(transactions, cfg6)
    second = _serialize(transactions, cfg6)
    assert first == second


def test_input_permutation_produces_identical_output(transactions, cfg6):
    """Output must depend on data + config, not on transaction ordering."""
    shuffled = list(reversed(transactions))
    assert _serialize(transactions, cfg6) == _serialize(shuffled, cfg6)
