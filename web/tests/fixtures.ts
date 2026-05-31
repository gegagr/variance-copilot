// Deterministic fixtures mirroring the Block 4 /view shapes (display strings already formatted).
// Lightweight JSON: only the fields the UI reads. Served via MSW.

type Cut = "prior_month_ytd" | "current_month" | "ytd" | "full_year";

export function makeFlag(over: Record<string, unknown>): Record<string, unknown> {
  return {
    schema_version: "1.0.0",
    line_type: "subtotal",
    direction: "favorable",
    rule_id: "value_default",
    pp_display: null,
    ...over,
  };
}

export const flags = [
  makeFlag({
    flag_id: "ebitda|ytd|current_vs_prior_year",
    reporting_line: "ebitda",
    time_cut: "ytd",
    scenario_pair: "current_vs_prior_year",
    current_display: "€78,600.00",
    comparator_display: "€66,000.00",
    abs_display: "€12,600.00",
    pct_display: "19.1%",
  }),
  makeFlag({
    flag_id: "revenue|ytd|current_vs_prior_year",
    reporting_line: "revenue",
    line_type: "revenue",
    time_cut: "ytd",
    scenario_pair: "current_vs_prior_year",
    current_display: "€161,280.00",
    comparator_display: "€144,000.00",
    abs_display: "€17,280.00",
    pct_display: "12.0%",
  }),
  makeFlag({
    flag_id: "ebitda|current_month|current_vs_budget",
    reporting_line: "ebitda",
    time_cut: "current_month",
    scenario_pair: "current_vs_budget",
    current_display: "€13,100.00",
    comparator_display: "€11,550.00",
    abs_display: "€1,550.00",
    pct_display: "13.4%",
  }),
];

function cells(line: string, isMargin: boolean) {
  const cuts: Cut[] = ["ytd", "current_month"];
  const out: Record<string, unknown>[] = [];
  for (const cut of cuts) {
    for (const [scenario, money, pct] of [
      ["prior_year", "€66,000.00", "45.8%"],
      ["current_year", "€78,600.00", "48.7%"],
      ["budget", "€69,300.00", "45.8%"],
    ] as const) {
      out.push({
        reporting_line: line,
        scenario,
        time_cut: cut,
        value: "0",
        display: isMargin ? pct : money,
        value_kind: "actual",
        is_margin: isMargin,
      });
    }
  }
  return out;
}

export const pnlView = {
  reporting_currency: "EUR",
  current_period: 6,
  lines: [
    { reporting_line: "revenue", order: 1, line_type: "revenue", cells: cells("revenue", false) },
    { reporting_line: "cogs", order: 2, line_type: "cost", cells: cells("cogs", false) },
    { reporting_line: "gross_profit", order: 3, line_type: "subtotal", cells: cells("gross_profit", false) },
    { reporting_line: "gross_margin_pct", order: 4, line_type: "margin", cells: cells("gross_margin_pct", true) },
    { reporting_line: "ebitda", order: 6, line_type: "subtotal", cells: cells("ebitda", false) },
  ],
};

export const DRAFT_COMMENTARY = "EBITDA outperformed prior year, reaching €78,600.00.";
export const QUESTION_TEXT = "Revenue is up €17,280.00 — is this the new enterprise contract?";
