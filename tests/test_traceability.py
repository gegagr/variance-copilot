"""T040: traceability test (SC-005 / Constitution II — Auditability)."""

from __future__ import annotations

from engine.models import SCENARIO_ORDER, TIMECUT_ORDER, LineType, Scenario, TimeCut
from engine.periods import periods_for


def test_every_leaf_cell_has_provenance_for_nonempty_periods(result6):
    prov = result6.provenance
    p = result6.current_period
    for line in result6.lines:
        if line.line_type not in (LineType.REVENUE, LineType.COST):
            continue
        for scenario in SCENARIO_ORDER:
            for tc in TIMECUT_ORDER:
                # current-year actuals only exist for periods 1..6 in the sample;
                # only assert non-empty where source periods exist for that scenario.
                if scenario is Scenario.CURRENT_YEAR and tc is not TimeCut.FULL_YEAR:
                    if not any(per <= 6 for per in periods_for(tc, p)):
                        continue
                ids = prov.get(line.reporting_line, scenario, tc)
                assert ids, f"no provenance for {line.reporting_line}/{scenario.value}/{tc.value}"


def test_subtotal_provenance_is_union_of_components(result6, cfg6):
    prov = result6.provenance
    layout = {row.reporting_line: row for row in cfg6.layout}
    for line in result6.lines:
        row = layout[line.reporting_line]
        if row.line_type is not LineType.SUBTOTAL:
            continue
        for scenario in SCENARIO_ORDER:
            for tc in TIMECUT_ORDER:
                sub_ids = set(prov.get(line.reporting_line, scenario, tc))
                union = set()
                for comp in row.components:
                    union |= set(prov.get(comp, scenario, tc))
                assert sub_ids == union


def test_provenance_ids_reference_real_transactions(result6, transactions):
    valid = {t.transaction_id for t in transactions}
    for ids in result6.provenance.by_cell.values():
        assert set(ids) <= valid
