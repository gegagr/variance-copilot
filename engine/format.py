"""Deterministic figure formatting (pure).

The ONLY place a figure becomes a display string. The ×100 for percentages happens here, in
Python, so the UI never performs arithmetic on a figure (Constitution: Determinism First at the
presentation layer). Output is a pure function of the input — no locale, no clock.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

_CENTS = Decimal("0.01")
_TENTH = Decimal("0.1")


def money(value: Decimal, currency_symbol: str = "€") -> str:
    """`Decimal("78600.00")` -> `"€78,600.00"` (grouping, 2dp, glyph)."""
    q = Decimal(value).quantize(_CENTS, rounding=ROUND_HALF_UP)
    return f"{currency_symbol}{q:,.2f}"


def percent(ratio: Decimal) -> str:
    """`Decimal("0.166667")` -> `"16.7%"` (ratio×100 in Python, 1dp)."""
    pct = (Decimal(ratio) * 100).quantize(_TENTH, rounding=ROUND_HALF_UP)
    return f"{pct:.1f}%"


def points(ratio: Decimal) -> str:
    """`Decimal("0.017857")` -> `"+1.8 pp"` (signed percentage points, 1dp)."""
    pts = (Decimal(ratio) * 100).quantize(_TENTH, rounding=ROUND_HALF_UP)
    return f"{pts:+.1f} pp"


def not_meaningful(label: str = "n/m") -> str:
    return label
