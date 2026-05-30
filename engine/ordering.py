"""Decimal precision and canonical-ordering helpers (pure).

Determinism (Constitution Principle I) requires that every figure be exact decimal
at a fixed precision and that every ordering be a function of the data, never of
incidental insertion or hash order.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

from engine.models import Transaction


def _quantum(precision: int) -> Decimal:
    """Return the Decimal quantum for ``precision`` decimal places, e.g. 2 -> 0.01."""
    return Decimal(1).scaleb(-precision)


def money(value: Decimal | int | str, precision: int) -> Decimal:
    """Quantize a monetary value to ``precision`` decimal places (banker-safe HALF_UP)."""
    return Decimal(value).quantize(_quantum(precision), rounding=ROUND_HALF_UP)


def ratio(value: Decimal | int | str, precision: int) -> Decimal:
    """Quantize a ratio (margin / percentage) to ``precision`` decimal places."""
    return Decimal(value).quantize(_quantum(precision), rounding=ROUND_HALF_UP)


def dsum(values: Iterable[Decimal]) -> Decimal:
    """Sum Decimals exactly. Decimal addition is exact and associative, so the
    result is independent of order; we still consume a concrete iterable."""
    total = Decimal(0)
    for v in values:
        total += v
    return total


def transaction_sort_key(t: Transaction) -> tuple:
    """Canonical, fully-specified sort key for a transaction (stable tie-break on id)."""
    return (
        t.scenario.value,
        t.entity,
        t.business_unit,
        t.gl_account,
        t.period,
        t.transaction_id,
    )


def canonical_transactions(transactions: Iterable[Transaction]) -> list[Transaction]:
    """Return transactions in canonical order (deterministic, stable)."""
    return sorted(transactions, key=transaction_sort_key)
