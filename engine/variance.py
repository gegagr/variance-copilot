"""compute_variances: current-vs-prior-year and current-vs-budget variances (pure).

Value lines carry absolute and percentage variances; margin lines carry a
percentage-point variance. Percentage uses an absolute-value denominator so the
magnitude is intuitive for negative bases; a zero comparator is "not meaningful".
Favorable/unfavorable is derived from line type, never the raw sign.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from config.schemas import EngineConfig
from engine import ordering
from engine.models import (
    COMPARATOR_SCENARIO,
    SCENARIO_PAIR_ORDER,
    TIMECUT_ORDER,
    Direction,
    LineType,
    PnLResult,
    Scenario,
    ScenarioPair,
    TimeCut,
    ValueKind,
    Variance,
)


def _direction(line_type: LineType, delta: Optional[Decimal]) -> Direction:
    """Favorable/unfavorable from the signed delta.

    Under the ``natural_signed`` convention (revenue positive, cost/expense negative),
    "higher is better" holds uniformly for every line type: more revenue is favorable,
    and a less-negative cost (lower spend) is also favorable. The cost sign is already
    carried by the amount, so no per-line-type inversion is needed — deriving direction
    from the signed delta is exactly "derived from line type" once the sign convention
    is applied. ``line_type`` is retained for forward compatibility with other
    conventions.
    """
    if delta is None or delta == 0:
        return "neutral"
    return "favorable" if delta > 0 else "unfavorable"


def compute_variances(result: PnLResult, config: EngineConfig) -> list[Variance]:
    rp = config.settings.ratio_precision

    # Index cells for O(1) lookup.
    cell = {
        (c.reporting_line, c.scenario, c.time_cut): c
        for line in result.lines
        for c in line.cells
    }
    line_type = {line.reporting_line: line.line_type for line in result.lines}

    variances: list[Variance] = []
    for line in result.lines:
        lt = line_type[line.reporting_line]
        is_margin = lt is LineType.MARGIN
        for time_cut in TIMECUT_ORDER:
            cur_cell = cell[(line.reporting_line, Scenario.CURRENT_YEAR, time_cut)]
            for pair in SCENARIO_PAIR_ORDER:
                cmp_cell = cell[
                    (line.reporting_line, COMPARATOR_SCENARIO[pair], time_cut)
                ]
                variances.append(
                    _build_variance(
                        line.reporting_line, lt, is_margin, time_cut, pair,
                        cur_cell.value, cmp_cell.value,
                        cur_cell.value_kind, cmp_cell.value_kind, rp,
                    )
                )
    return variances


def _build_variance(
    reporting_line: str,
    line_type: LineType,
    is_margin: bool,
    time_cut: TimeCut,
    pair: ScenarioPair,
    current: Decimal,
    comparator: Decimal,
    current_kind: ValueKind,
    comparator_kind: ValueKind,
    rp: int,
) -> Variance:
    abs_variance: Optional[Decimal] = None
    pct_variance: Optional[Decimal] = None
    pp_variance: Optional[Decimal] = None
    is_meaningful = True

    if is_margin:
        not_meaningful = (
            current_kind is ValueKind.NOT_MEANINGFUL
            or comparator_kind is ValueKind.NOT_MEANINGFUL
        )
        if not_meaningful:
            is_meaningful = False
        else:
            pp_variance = ordering.ratio(current - comparator, rp)
        delta = pp_variance
    else:
        abs_variance = current - comparator
        if comparator == 0:
            is_meaningful = False  # percentage not meaningful
        else:
            pct_variance = ordering.ratio(abs_variance / abs(comparator), rp)
        delta = abs_variance

    return Variance(
        reporting_line=reporting_line,
        line_type=line_type,
        time_cut=time_cut,
        scenario_pair=pair,
        current_value=current,
        comparator_value=comparator,
        abs_variance=abs_variance,
        pct_variance=pct_variance,
        pp_variance=pp_variance,
        is_meaningful=is_meaningful,
        direction=_direction(line_type, delta),
    )
