# Test suite — Success Criteria traceability

Every Success Criterion (SC) from the spec maps to at least one test.

| SC | Criterion | Covering test(s) |
|----|-----------|------------------|
| SC-001 | Reproducible (byte-identical) output | `test_determinism.py::test_identical_inputs_produce_identical_output` |
| SC-002 | Subtotals = Σ components; margins = numerator/base | `test_reconciliation.py::test_subtotals_equal_sum_of_components`, `::test_margins_equal_numerator_over_base` |
| SC-003 | Ties to source, zero residual | `test_reconciliation.py::test_ties_to_source_zero_residual`, `::test_grand_total_ebit_ties_to_all_mapped_transactions` |
| SC-004 | Unmapped GL accounts surfaced, never dropped | `test_edge_cases.py::test_unmapped_accounts_surfaced_not_dropped` |
| SC-005 | Every figure traceable to source transactions | `test_traceability.py` (all) |
| SC-006 | Restructure via config only (no code) | `test_scenarios.py` runs the same code at different `current_period`; edge tests build alternate layouts via config objects only |
| SC-007 | Landing = elapsed actual + remaining budget, labeled | `test_scenarios.py::test_landing_is_elapsed_actual_plus_remaining_budget`, `::test_landing_label_present_on_all_current_year_full_year_cells` |
| SC-008 | Flags carry all fields + validate against schema | `test_flagging.py::test_flag_has_all_required_fields`, `test_contract_flagged_variance.py` |
| SC-009 | Empty periods, zero-base margins, zero comparators handled | `test_scenarios.py::test_boundary_first_period_empty_prior_month_ytd`, `test_edge_cases.py::test_zero_base_margin_marked_not_meaningful`, `test_variance.py::test_zero_comparator_marked_not_meaningful` |
| SC-010 | Excel parity (no value differences) | `test_excel_export.py::test_excel_preserves_structure_and_figures` |

Constitution guards: Principle I (Determinism) → `test_determinism.py`; Principle II
(Auditability) → `test_traceability.py`; functional-core purity / no-LLM →
`test_architecture.py`; FR-017 public contract drift → `test_contract_flagged_variance.py`.

Run: `uv run pytest`
