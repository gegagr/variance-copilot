"""flag_variances: materiality flagging against configurable thresholds (pure).

Only DETAIL lines (revenue | cost leaf lines) are flagged for investigation — a detail line
is flagged when its absolute AND its percentage variance breach their thresholds (de-minimis
guard). Subtotals and margins are NEVER flagged (they are roll-ups of detail lines; the agent
investigates the underlying detail). Variances are still computed for every row for the grid;
flagging is the narrower act. Each flag is a versioned :class:`FlaggedVariance`.
"""

from __future__ import annotations

from config.schemas import EngineConfig, ThresholdRow
from engine.models import (
    SCENARIO_PAIR_ORDER,
    TIMECUT_ORDER,
    FlaggedVariance,
    LineType,
    Variance,
)

# Only these line types are detail lines eligible for flagging.
DETAIL_LINE_TYPES = (LineType.REVENUE, LineType.COST)


def flag_variances(variances: list[Variance], config: EngineConfig) -> list[FlaggedVariance]:
    rules: dict[str, ThresholdRow] = {r.applies_to: r for r in config.thresholds}

    # Deterministic output order: by time cut, scenario pair, then reporting line.
    timecut_rank = {tc: i for i, tc in enumerate(TIMECUT_ORDER)}
    pair_rank = {p: i for i, p in enumerate(SCENARIO_PAIR_ORDER)}
    ordered = sorted(
        variances,
        key=lambda v: (timecut_rank[v.time_cut], pair_rank[v.scenario_pair], v.reporting_line),
    )

    flags: list[FlaggedVariance] = []
    for v in ordered:
        # Only detail lines are flagged — never subtotals or margins.
        if v.line_type not in DETAIL_LINE_TYPES:
            continue
        if v.direction not in ("favorable", "unfavorable"):
            continue  # neutral / no movement never flags
        rule = rules.get("value")
        if rule is None:
            continue

        if v.abs_variance is None or v.pct_variance is None:
            continue  # percentage not meaningful (zero comparator) -> cannot confirm both
        breach = (
            abs(v.abs_variance) >= rule.abs_threshold
            and abs(v.pct_variance) >= rule.pct_threshold
        )

        if not breach:
            continue

        flags.append(
            FlaggedVariance(
                flag_id=f"{v.reporting_line}|{v.time_cut.value}|{v.scenario_pair.value}|{rule.rule_id}",
                reporting_line=v.reporting_line,
                line_type=v.line_type,
                time_cut=v.time_cut,
                scenario_pair=v.scenario_pair,
                current_value=v.current_value,
                comparator_value=v.comparator_value,
                abs_variance=v.abs_variance,
                pct_variance=v.pct_variance,
                pp_variance=v.pp_variance,
                direction=v.direction,  # narrowed to favorable/unfavorable above
                rule_id=rule.rule_id,
                abs_threshold=rule.abs_threshold,
                pct_threshold=rule.pct_threshold,
                pp_threshold=rule.pp_threshold,
            )
        )
    return flags
