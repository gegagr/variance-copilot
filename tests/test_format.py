"""Block 5 dependency: deterministic figure formatting (engine/format.py)."""

from __future__ import annotations

from decimal import Decimal

from engine import format as fmt


def test_money():
    assert fmt.money(Decimal("78600.00")) == "€78,600.00"
    assert fmt.money(Decimal("66000.00")) == "€66,000.00"
    assert fmt.money(Decimal("-2880.00")) == "€-2,880.00"
    assert fmt.money(Decimal("0.00")) == "€0.00"


def test_percent():
    assert fmt.percent(Decimal("0.166667")) == "16.7%"
    assert fmt.percent(Decimal("0.12")) == "12.0%"
    assert fmt.percent(Decimal("-0.06")) == "-6.0%"


def test_points():
    assert fmt.points(Decimal("0.017857")) == "+1.8 pp"
    assert fmt.points(Decimal("-0.02")) == "-2.0 pp"


def test_not_meaningful():
    assert fmt.not_meaningful() == "n/m"
    assert fmt.not_meaningful("n/a") == "n/a"


def test_deterministic():
    assert fmt.money(Decimal("78600.00")) == fmt.money(Decimal("78600.00"))
