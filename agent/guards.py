"""The traceability guard — deterministic enforcement that the LLM never produces a number.

Two pure checks:
- `assert_no_raw_digits`: the model's tokenized narrative must contain NO digit outside a
  `{{fig:...}}` token (the model emits references, never literals).
- `assert_grounded`: every number in the FULLY RENDERED text must be a verbatim source value
  (a Block 1 figure or a GL amount) or a code-computed aggregate — i.e. present in the allowed
  set. Anything else rejects the output.

Money figures are recognised by a `€` prefix, a decimal point, or thousands grouping (so bare
years/ids/dates are not mistaken for figures). Percentages are recognised by a trailing `%`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

TOKEN_RE = re.compile(r"\{\{[^}]*\}\}")
DIGIT_RE = re.compile(r"\d")

# A percentage: digits (optionally grouped/decimal) followed by %.
PERCENT_RE = re.compile(r"[+-]?\d[\d,]*(?:\.\d+)?\s*%")
# Money: requires a € sign, OR a decimal point, OR thousands grouping — never a bare integer.
MONEY_RE = re.compile(r"€\s*[+-]?\d[\d,]*(?:\.\d+)?|[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[+-]?\d+\.\d+")


@dataclass
class AllowedValues:
    money: set[Decimal] = field(default_factory=set)
    ratio: set[Decimal] = field(default_factory=set)

    def add_money(self, v: Decimal) -> None:
        self.money.add(Decimal(v))

    def add_ratio(self, v: Decimal) -> None:
        self.ratio.add(Decimal(v))


@dataclass
class GuardResult:
    ok: bool
    offending: list[str] = field(default_factory=list)


def assert_no_raw_digits(tokenized_text: str) -> GuardResult:
    """Fail if any digit appears outside a `{{...}}` token."""
    stripped = TOKEN_RE.sub("", tokenized_text)
    offenders = DIGIT_RE.findall(stripped)
    return GuardResult(ok=not offenders, offending=sorted(set(offenders)))


def _to_decimal(raw: str) -> Decimal:
    cleaned = raw.replace("€", "").replace(",", "").replace("%", "").strip()
    return Decimal(cleaned)


def draft_omits_available_evidence(record, evidence_available: bool) -> bool:
    """True (a bug) when a DRAFT is emitted with NO GL evidence gathered, yet rows exist.

    A draft that explains a variance while ignoring the GL rows actually behind it — e.g. claims
    "no transactions" when the driver rows exist for that line/period — is not grounded. The caller
    passes whether the flag's deterministic GL slice (``grounded_gl_query``) returns any rows.
    """
    if record is None or record.draft is None:
        return False
    return evidence_available and not record.evidence


def assert_grounded(text: str, allowed: AllowedValues) -> GuardResult:
    """Every figure in rendered `text` must be in the allowed set (verbatim or aggregate)."""
    offending: list[str] = []
    remaining = text

    # Percentages first (and remove them so the money pass can't re-read the digits).
    for match in PERCENT_RE.findall(text):
        try:
            value = _to_decimal(match) / Decimal(100)
        except InvalidOperation:
            offending.append(match)
            continue
        if value not in allowed.ratio:
            offending.append(match.strip())
    remaining = PERCENT_RE.sub(" ", remaining)

    # Money / decimal-grouped figures.
    for match in MONEY_RE.findall(remaining):
        try:
            value = _to_decimal(match)
        except InvalidOperation:
            offending.append(match)
            continue
        if value not in allowed.money:
            offending.append(match.strip())

    return GuardResult(ok=not offending, offending=offending)
