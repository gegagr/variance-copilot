"""query_gl_detail — the agent's only read-only window into GL detail (agent core).

Pure logic: resolves a reporting line to its GL accounts via the Block 1 chart-of-accounts
config and filters injected GL rows. Performs NO I/O itself — the rows come from an injected
repository (the data layer reads the files). Read-only.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable, Protocol

from config.schemas import EngineConfig
from engine.models import LineType, Scenario, TimeCut
from engine.periods import periods_for
from agent.models import GLEvidenceRow, GLQuery, GLQueryResult


class GLRowSource(Protocol):
    def get_gl_rows(self) -> list[GLEvidenceRow]: ...


# JSON tool schema exposed to the model.
QUERY_GL_DETAIL_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "query_gl_detail",
        "description": "Return the GL transaction rows behind a reporting line for the "
        "variance's slice. Pass the flag's own dimensions (time_cut + scenario_pair); the "
        "current side of every comparison resolves to current-year actuals. Optionally pass "
        "an explicit period + scenario instead.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["reporting_line"],
            "properties": {
                "reporting_line": {"type": "string"},
                "time_cut": {
                    "type": "string",
                    "enum": ["prior_month_ytd", "current_month", "ytd", "full_year"],
                },
                "scenario_pair": {
                    "type": "string",
                    "enum": ["current_vs_prior_year", "current_vs_budget"],
                },
                "period": {"type": "integer", "minimum": 1, "maximum": 12},
                "scenario": {"type": "string", "enum": ["prior_year", "current_year", "budget"]},
                "filters": {
                    "type": "object",
                    "properties": {
                        "project": {"type": "string"},
                        "counterparty": {"type": "string"},
                        "label": {"type": "string"},
                    },
                },
            },
        },
    },
}


def gl_accounts_for(config: EngineConfig, reporting_line: str) -> set[str]:
    """Resolve a reporting line to the set of GL accounts beneath it (leaf accounts)."""
    by_name = {r.reporting_line: r for r in config.layout}
    coa_by_line: dict[str, set[str]] = defaultdict(set)
    for row in config.coa:
        coa_by_line[row.reporting_line].add(row.gl_account)

    accounts: set[str] = set()

    def visit(name: str) -> None:
        row = by_name[name]
        if row.line_type in (LineType.REVENUE, LineType.COST):
            accounts.update(coa_by_line.get(name, set()))
        elif row.line_type is LineType.SUBTOTAL:
            for comp in row.components:
                visit(comp)
        elif row.line_type is LineType.MARGIN:
            if row.margin_numerator:
                visit(row.margin_numerator)
            if row.margin_base:
                visit(row.margin_base)

    visit(reporting_line)
    return accounts


def _matches_filters(row: GLEvidenceRow, filters: dict | None) -> bool:
    if not filters:
        return True
    if "project" in filters and row.project != filters["project"]:
        return False
    if "counterparty" in filters and row.counterparty != filters["counterparty"]:
        return False
    if "label" in filters and filters["label"] not in row.labels:
        return False
    return True


def resolve_scope(config: EngineConfig, query: GLQuery) -> tuple[str, set[int]]:
    """Translate a query's dimensions into concrete GL columns (scenario, periods).

    Mirrors exactly how the engine's aggregation resolves the same dimensions
    (``engine.periods.periods_for`` for the time cut; the current side of every
    comparison is current-year actuals). The flag carries ``time_cut`` /
    ``scenario_pair`` — never the data's ``period`` / ``scenario`` — so without this
    translation the filters match nothing.
    """
    # Scenario: an explicit value wins (lets the agent also pull the budget side);
    # otherwise a scenario_pair resolves to the CURRENT side = current-year actuals.
    if query.scenario is not None:
        scenario = query.scenario
    elif query.scenario_pair is not None:
        scenario = Scenario.CURRENT_YEAR.value
    else:
        scenario = Scenario.CURRENT_YEAR.value

    # Periods: a time_cut resolves against the current period exactly as the engine
    # aggregates it; otherwise an explicit single period; otherwise the current period.
    current_period = (
        query.current_period
        if query.current_period is not None
        else config.settings.current_period
    )
    if query.time_cut is not None:
        periods = set(periods_for(TimeCut(query.time_cut), current_period))
    elif query.period is not None:
        periods = {query.period}
    else:
        periods = {current_period}

    return scenario, periods


def query_gl_detail(repo: GLRowSource, config: EngineConfig, query: GLQuery) -> GLQueryResult:
    """Read-only: return the GL rows behind a reporting line for the variance's slice.

    Resolves the query's dimensions to concrete (scenario, periods) before filtering,
    so a flag's ``time_cut`` / ``scenario_pair`` map to the GL's ``period`` / ``scenario``.
    """
    accounts = gl_accounts_for(config, query.reporting_line)
    scenario, periods = resolve_scope(config, query)
    rows = [
        row
        for row in repo.get_gl_rows()
        if row.gl_account in accounts
        and row.scenario == scenario
        and row.period in periods
        and _matches_filters(row, query.filters)
    ]
    rows.sort(key=lambda r: r.transaction_id)  # canonical order
    return GLQueryResult(query=query, rows=rows)


def make_gl_tool(repo: GLRowSource, config: EngineConfig) -> Callable[[GLQuery], GLQueryResult]:
    """Bind the tool to a repository + config, yielding the callable the loop invokes."""
    def _tool(query: GLQuery) -> GLQueryResult:
        return query_gl_detail(repo, config, query)

    return _tool
