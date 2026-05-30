"""build_pnl: the deterministic P&L builder (pure core).

Maps GL accounts to reporting lines, aggregates leaf lines, computes subtotals and
margins, produces the full scenario x time-cut grid (including the labeled landing),
and returns a fully traceable, reconciled :class:`PnLResult`.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from config.schemas import EngineConfig, PnLLayoutRow
from engine import ordering, periods
from engine.models import (
    SCENARIO_ORDER,
    TIMECUT_ORDER,
    LineType,
    PnLCell,
    PnLLine,
    PnLResult,
    ProvenanceIndex,
    ReconciliationStatus,
    Scenario,
    TimeCut,
    Transaction,
    ValueKind,
)


def build_pnl(transactions: list[Transaction], config: EngineConfig) -> PnLResult:
    settings = config.settings
    p = settings.current_period
    mp, rp = settings.money_precision, settings.ratio_precision

    coa = {row.gl_account: row.reporting_line for row in config.coa}
    layout = sorted(config.layout, key=lambda r: r.order)
    by_name: dict[str, PnLLayoutRow] = {r.reporting_line: r for r in layout}

    # --- 1. Map transactions to reporting lines; surface unmapped accounts. -------
    # Leaf buckets keyed by (reporting_line, scenario, period).
    bucket_sum: dict[tuple[str, Scenario, int], Decimal] = defaultdict(lambda: Decimal(0))
    bucket_ids: dict[tuple[str, Scenario, int], list[str]] = defaultdict(list)
    unmapped: dict[str, Decimal] = defaultdict(lambda: Decimal(0))

    for t in ordering.canonical_transactions(transactions):
        line = coa.get(t.gl_account)
        if line is None:
            unmapped[t.gl_account] += t.amount
            continue
        key = (line, t.scenario, t.period)
        bucket_sum[key] += t.amount
        bucket_ids[key].append(t.transaction_id)

    # --- 2. Cell computation (memoized; subtotals/margins resolve transitively). --
    computed: dict[tuple[str, Scenario, TimeCut], dict] = {}

    def leaf_cell(line: str, scenario: Scenario, time_cut: TimeCut) -> tuple[Decimal, set[str]]:
        total = Decimal(0)
        ids: set[str] = set()
        for src_scenario, prds in periods.contributions(scenario, time_cut, p):
            for per in prds:
                key = (line, src_scenario, per)
                if key in bucket_sum:
                    total += bucket_sum[key]
                    ids.update(bucket_ids[key])
        return total, ids

    def compute(line: str, scenario: Scenario, time_cut: TimeCut) -> dict:
        cache_key = (line, scenario, time_cut)
        if cache_key in computed:
            return computed[cache_key]

        row = by_name[line]
        if row.line_type in (LineType.REVENUE, LineType.COST):
            total, ids = leaf_cell(line, scenario, time_cut)
            res = {
                "value": ordering.money(total, mp),
                "ids": ids,
                "is_margin": False,
                "value_kind": periods.value_kind(scenario, time_cut, False, False),
            }
        elif row.line_type is LineType.SUBTOTAL:
            total = Decimal(0)
            ids = set()
            for comp in row.components:
                c = compute(comp, scenario, time_cut)
                total += c["value"]
                ids |= c["ids"]
            res = {
                "value": ordering.money(total, mp),
                "ids": ids,
                "is_margin": False,
                "value_kind": periods.value_kind(scenario, time_cut, False, False),
            }
        elif row.line_type is LineType.MARGIN:
            num = compute(row.margin_numerator, scenario, time_cut)
            base = compute(row.margin_base, scenario, time_cut)
            ids = num["ids"] | base["ids"]
            if base["value"] == 0:
                res = {
                    "value": Decimal(0),
                    "ids": ids,
                    "is_margin": True,
                    "value_kind": ValueKind.NOT_MEANINGFUL,
                }
            else:
                res = {
                    "value": ordering.ratio(num["value"] / base["value"], rp),
                    "ids": ids,
                    "is_margin": True,
                    "value_kind": periods.value_kind(scenario, time_cut, True, False),
                }
        else:  # pragma: no cover - guarded by config validation
            raise ValueError(f"Unknown line type: {row.line_type}")

        computed[cache_key] = res
        return res

    # --- 3. Assemble ordered lines + cells, and the provenance index. -------------
    lines: list[PnLLine] = []
    provenance = ProvenanceIndex()
    for row in layout:
        cells: list[PnLCell] = []
        for scenario in SCENARIO_ORDER:
            for time_cut in TIMECUT_ORDER:
                res = compute(row.reporting_line, scenario, time_cut)
                cells.append(
                    PnLCell(
                        reporting_line=row.reporting_line,
                        scenario=scenario,
                        time_cut=time_cut,
                        value=res["value"],
                        value_kind=res["value_kind"],
                        is_margin=res["is_margin"],
                    )
                )
                provenance.by_cell[
                    ProvenanceIndex.key(row.reporting_line, scenario, time_cut)
                ] = sorted(res["ids"])
        lines.append(
            PnLLine(
                reporting_line=row.reporting_line,
                order=row.order,
                line_type=row.line_type,
                cells=cells,
            )
        )

    # --- 4. Reconciliation status. ------------------------------------------------
    residual = ordering.money(ordering.dsum(unmapped.values()), mp)
    reconciliation = ReconciliationStatus(
        is_complete=len(unmapped) == 0,
        residual=residual,
        unmapped_accounts={gl: ordering.money(amt, mp) for gl, amt in sorted(unmapped.items())},
    )

    return PnLResult(
        lines=lines,
        reconciliation=reconciliation,
        provenance=provenance,
        reporting_currency=settings.reporting_currency,
        current_period=p,
    )
