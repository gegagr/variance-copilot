"""query_gl_detail — the agent's only read-only window into GL detail (agent core).

Pure logic: resolves a reporting line to its GL accounts via the Block 1 chart-of-accounts
config and filters injected GL rows. Performs NO I/O itself — the rows come from an injected
repository (the data layer reads the files). Read-only.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable, Protocol

from config.schemas import EngineConfig
from engine.models import LineType
from agent.models import GLEvidenceRow, GLQuery, GLQueryResult


class GLRowSource(Protocol):
    def get_gl_rows(self) -> list[GLEvidenceRow]: ...


# JSON tool schema exposed to the model.
QUERY_GL_DETAIL_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "query_gl_detail",
        "description": "Return the GL transaction rows behind a reporting line / period / scenario.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["reporting_line", "period", "scenario"],
            "properties": {
                "reporting_line": {"type": "string"},
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


def query_gl_detail(repo: GLRowSource, config: EngineConfig, query: GLQuery) -> GLQueryResult:
    """Read-only: return the GL rows behind (reporting_line, period, scenario)."""
    accounts = gl_accounts_for(config, query.reporting_line)
    rows = [
        row
        for row in repo.get_gl_rows()
        if row.gl_account in accounts
        and row.scenario == query.scenario
        and row.period == query.period
        and _matches_filters(row, query.filters)
    ]
    rows.sort(key=lambda r: r.transaction_id)  # canonical order
    return GLQueryResult(query=query, rows=rows)


def make_gl_tool(repo: GLRowSource, config: EngineConfig) -> Callable[[GLQuery], GLQueryResult]:
    """Bind the tool to a repository + config, yielding the callable the loop invokes."""
    def _tool(query: GLQuery) -> GLQueryResult:
        return query_gl_detail(repo, config, query)

    return _tool
