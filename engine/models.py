"""Domain types and output models for the deterministic P&L engine.

This module is part of the PURE functional core: it performs no I/O. All monetary
values and ratios are ``Decimal`` (never float). Enum orderings here are the single
source of canonical output ordering, which is what makes the engine's output
byte-identical across runs (Constitution Principle I — Determinism First).
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


# --------------------------------------------------------------------------- #
# Enumerations (define canonical order)
# --------------------------------------------------------------------------- #
class Scenario(str, Enum):
    PRIOR_YEAR = "prior_year"
    CURRENT_YEAR = "current_year"
    BUDGET = "budget"


class TimeCut(str, Enum):
    PRIOR_MONTH_YTD = "prior_month_ytd"
    CURRENT_MONTH = "current_month"
    YTD = "ytd"
    FULL_YEAR = "full_year"


class LineType(str, Enum):
    REVENUE = "revenue"      # positive delta = favorable
    COST = "cost"            # positive delta = unfavorable
    SUBTOTAL = "subtotal"    # treated as a value line; higher = favorable
    MARGIN = "margin"        # ratio line; variance in percentage points


class ValueKind(str, Enum):
    ACTUAL = "actual"
    BUDGET = "budget"
    LANDING = "landing"            # current-year full-year only
    NOT_MEANINGFUL = "not_meaningful"  # zero-base margin marker


class ScenarioPair(str, Enum):
    CURRENT_VS_PRIOR_YEAR = "current_vs_prior_year"
    CURRENT_VS_BUDGET = "current_vs_budget"


# Canonical orderings used everywhere output is produced.
SCENARIO_ORDER: tuple[Scenario, ...] = (
    Scenario.PRIOR_YEAR,
    Scenario.CURRENT_YEAR,
    Scenario.BUDGET,
)
TIMECUT_ORDER: tuple[TimeCut, ...] = (
    TimeCut.PRIOR_MONTH_YTD,
    TimeCut.CURRENT_MONTH,
    TimeCut.YTD,
    TimeCut.FULL_YEAR,
)
SCENARIO_PAIR_ORDER: tuple[ScenarioPair, ...] = (
    ScenarioPair.CURRENT_VS_PRIOR_YEAR,
    ScenarioPair.CURRENT_VS_BUDGET,
)

# Comparator scenario for each pair.
COMPARATOR_SCENARIO: dict[ScenarioPair, Scenario] = {
    ScenarioPair.CURRENT_VS_PRIOR_YEAR: Scenario.PRIOR_YEAR,
    ScenarioPair.CURRENT_VS_BUDGET: Scenario.BUDGET,
}

Direction = Literal["favorable", "unfavorable", "neutral"]


# --------------------------------------------------------------------------- #
# Input model (the engine's input contract)
# --------------------------------------------------------------------------- #
class Transaction(BaseModel):
    model_config = ConfigDict(frozen=True)

    transaction_id: str
    gl_account: str
    amount: Decimal
    period: int  # 1..12 (fiscal month)
    scenario: Scenario
    entity: str
    business_unit: str
    project: Optional[str] = None


# --------------------------------------------------------------------------- #
# Output models
# --------------------------------------------------------------------------- #
class PnLCell(BaseModel):
    reporting_line: str
    scenario: Scenario
    time_cut: TimeCut
    value: Decimal
    value_kind: ValueKind
    is_margin: bool = False


class PnLLine(BaseModel):
    reporting_line: str
    order: int
    line_type: LineType
    cells: list[PnLCell]


class ReconciliationStatus(BaseModel):
    is_complete: bool
    residual: Decimal
    unmapped_accounts: dict[str, Decimal] = {}


class ProvenanceIndex(BaseModel):
    """Maps each cell to the contributing transaction ids.

    Keyed by the string ``f"{reporting_line}|{scenario}|{time_cut}"`` so the model
    remains JSON-serializable while still giving full traceability for every cell
    (Constitution Principle II — Auditability).
    """

    by_cell: dict[str, list[str]] = {}

    @staticmethod
    def key(reporting_line: str, scenario: Scenario, time_cut: TimeCut) -> str:
        return f"{reporting_line}|{scenario.value}|{time_cut.value}"

    def get(self, reporting_line: str, scenario: Scenario, time_cut: TimeCut) -> list[str]:
        return self.by_cell.get(self.key(reporting_line, scenario, time_cut), [])


class PnLResult(BaseModel):
    lines: list[PnLLine]
    reconciliation: ReconciliationStatus
    provenance: ProvenanceIndex
    reporting_currency: Literal["EUR"] = "EUR"
    current_period: int


class Variance(BaseModel):
    reporting_line: str
    line_type: LineType
    time_cut: TimeCut
    scenario_pair: ScenarioPair
    current_value: Decimal
    comparator_value: Decimal
    abs_variance: Optional[Decimal] = None
    pct_variance: Optional[Decimal] = None
    pp_variance: Optional[Decimal] = None
    is_meaningful: bool = True
    direction: Direction = "neutral"


class FlaggedVariance(BaseModel):
    """Versioned PUBLIC CONTRACT consumed by Block 3 (the AI layer).

    Decimal fields serialize as strings in JSON mode (Pydantic v2 default) to
    preserve exact precision across the block boundary. Do not change this shape
    without bumping ``schema_version`` and the committed JSON Schema.
    """

    schema_version: Literal["1.0.0"] = "1.0.0"
    flag_id: str
    reporting_line: str
    line_type: LineType
    time_cut: TimeCut
    scenario_pair: ScenarioPair
    current_value: Decimal
    comparator_value: Decimal
    abs_variance: Optional[Decimal] = None
    pct_variance: Optional[Decimal] = None
    pp_variance: Optional[Decimal] = None
    direction: Literal["favorable", "unfavorable"]
    rule_id: str
    abs_threshold: Decimal
    pct_threshold: Decimal
    pp_threshold: Decimal
