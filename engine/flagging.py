"""flag_variances: materiality flagging against configurable thresholds (pure).

Combination logic (clarified): a VALUE line (revenue | cost | subtotal) is flagged
only when its absolute AND its percentage variance breach their thresholds
(de-minimis guard); a MARGIN line is flagged when its percentage-point variance
breaches the pp threshold. Each flag is a versioned :class:`FlaggedVariance`.
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


def _category(line_type: LineType) -> str:
    return "margin" if line_type is LineType.MARGIN else "value"


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
        if v.direction not in ("favorable", "unfavorable"):
            continue  # neutral / no movement never flags
        rule = rules.get(_category(v.line_type))
        if rule is None:
            continue

        if v.line_type is LineType.MARGIN:
            if v.pp_variance is None:
                continue
            breach = abs(v.pp_variance) >= rule.pp_threshold
        else:
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
