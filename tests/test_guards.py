"""Phase 3: the traceability guard — happy path + adversarial (the constitution's hard line)."""

from __future__ import annotations

from decimal import Decimal

from agent.guards import AllowedValues, assert_grounded, assert_no_raw_digits


def _allowed():
    a = AllowedValues()
    a.add_money(Decimal("161280.00"))
    a.add_money(Decimal("144000.00"))
    a.add_ratio(Decimal("0.120000"))
    return a


# --- assert_no_raw_digits ------------------------------------------------------
def test_no_raw_digits_passes_when_figures_are_tokens():
    text = "EBITDA rose to {{fig:flag.current_value}} from {{fig:flag.comparator_value}}."
    assert assert_no_raw_digits(text).ok


def test_no_raw_digits_fails_on_a_literal_number():
    res = assert_no_raw_digits("EBITDA rose by 5% versus budget")
    assert res.ok is False
    assert "5" in res.offending


# --- assert_grounded: happy path ----------------------------------------------
def test_grounded_passes_for_source_values():
    text = "EBITDA €161,280.00 vs €144,000.00, up 12%."
    assert assert_grounded(text, _allowed()).ok


def test_grounded_passes_negative_money():
    a = AllowedValues()
    a.add_money(Decimal("-2880.00"))
    assert assert_grounded("Cost delta €-2,880.00.", a).ok


# --- assert_grounded: ADVERSARIAL ---------------------------------------------
def test_grounded_rejects_number_absent_from_sources():
    res = assert_grounded("EBITDA €999,999.00 this period.", _allowed())
    assert res.ok is False
    assert any("999,999" in o for o in res.offending)


def test_grounded_rejects_disguised_decimal():
    res = assert_grounded("It was 12345.67 in total.", _allowed())
    assert res.ok is False


def test_grounded_rejects_wrong_percentage():
    res = assert_grounded("Margin up 7%.", _allowed())  # 0.07 not allowed
    assert res.ok is False


def test_grounded_normalizes_grouping_and_currency():
    # Same value, disguised with symbol + grouping, must still match.
    a = AllowedValues()
    a.add_money(Decimal("161280.00"))
    assert assert_grounded("€161,280.00", a).ok
    assert assert_grounded("161280.00", a).ok  # no symbol, decimal present


def test_grounded_ignores_bare_years_and_ids():
    # A bare integer (year/id) is not a figure and must not trip the guard.
    a = AllowedValues()
    a.add_money(Decimal("161280.00"))
    assert assert_grounded("In 2025 the figure was €161,280.00 (id 4000).", a).ok
