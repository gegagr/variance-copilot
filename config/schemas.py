"""Pydantic v2 schemas for the engine's configuration, plus structural validation.

These models are pure (no I/O). The shell loader (``config/loader.py``) reads files
and constructs an :class:`EngineConfig`; :func:`validate_config` then enforces the
cross-row invariants (Constitution Principle V — Config-Driven; FR-024).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel

from engine.models import LineType


class ConfigError(ValueError):
    """Raised when configuration is internally inconsistent (duplicate / cyclic / dangling)."""


class CoaMappingRow(BaseModel):
    gl_account: str
    reporting_line: str


class BusinessUnitRow(BaseModel):
    business_unit: str
    parent: Optional[str] = None


class EntityGeographyRow(BaseModel):
    entity: str
    geography: str
    rollup: str


class PnLLayoutRow(BaseModel):
    reporting_line: str
    order: int
    line_type: LineType
    components: list[str] = []          # subtotals only
    margin_numerator: Optional[str] = None  # margins only
    margin_base: Optional[str] = None       # margins only


class ThresholdRow(BaseModel):
    rule_id: str
    applies_to: Literal["value", "margin"]
    abs_threshold: Decimal
    pct_threshold: Decimal
    pp_threshold: Decimal


class ReportingSettings(BaseModel):
    reporting_currency: Literal["EUR"] = "EUR"
    money_precision: int = 2
    ratio_precision: int = 6
    current_period: int = 12
    not_meaningful_label: str = "n/m"
    sign_convention: Literal["natural_signed"] = "natural_signed"


class EngineConfig(BaseModel):
    coa: list[CoaMappingRow]
    business: list[BusinessUnitRow]
    entities: list[EntityGeographyRow]
    layout: list[PnLLayoutRow]
    thresholds: list[ThresholdRow]
    settings: ReportingSettings


def validate_config(config: EngineConfig) -> EngineConfig:
    """Enforce cross-row invariants. Raises :class:`ConfigError` on any violation."""
    layout = config.layout
    names = [row.reporting_line for row in layout]

    # Unique reporting lines and unique order.
    if len(names) != len(set(names)):
        raise ConfigError("Duplicate reporting_line in P&L layout.")
    orders = [row.order for row in layout]
    if len(orders) != len(set(orders)):
        raise ConfigError("Duplicate order value in P&L layout.")

    name_set = set(names)
    by_name = {row.reporting_line: row for row in layout}

    # Chart-of-accounts: each GL account mapped exactly once, to an existing leaf line.
    seen_gl: set[str] = set()
    leaf_types = {LineType.REVENUE, LineType.COST}
    for row in config.coa:
        if row.gl_account in seen_gl:
            raise ConfigError(f"GL account {row.gl_account!r} mapped more than once.")
        seen_gl.add(row.gl_account)
        if row.reporting_line not in name_set:
            raise ConfigError(
                f"GL account {row.gl_account!r} maps to unknown reporting line "
                f"{row.reporting_line!r}."
            )
        if by_name[row.reporting_line].line_type not in leaf_types:
            raise ConfigError(
                f"GL account {row.gl_account!r} must map to a revenue/cost leaf line, "
                f"not {by_name[row.reporting_line].line_type.value} line "
                f"{row.reporting_line!r}."
            )

    # Subtotal components and margin numerator/base reference existing lines.
    for row in layout:
        if row.line_type is LineType.SUBTOTAL:
            if not row.components:
                raise ConfigError(f"Subtotal {row.reporting_line!r} has no components.")
            for comp in row.components:
                if comp not in name_set:
                    raise ConfigError(
                        f"Subtotal {row.reporting_line!r} references unknown line {comp!r}."
                    )
        elif row.line_type is LineType.MARGIN:
            for ref, label in ((row.margin_numerator, "numerator"), (row.margin_base, "base")):
                if ref is None:
                    raise ConfigError(f"Margin {row.reporting_line!r} missing {label}.")
                if ref not in name_set:
                    raise ConfigError(
                        f"Margin {row.reporting_line!r} {label} references unknown line {ref!r}."
                    )

    # Subtotal dependency graph must be acyclic.
    _assert_acyclic_subtotals(by_name)

    # Business-unit hierarchy: parents exist and the graph is acyclic.
    _assert_business_hierarchy(config.business)

    # Thresholds: at most one rule per category, and each category present is usable.
    by_category: dict[str, ThresholdRow] = {}
    for row in config.thresholds:
        if row.applies_to in by_category:
            raise ConfigError(f"Multiple threshold rules for category {row.applies_to!r}.")
        by_category[row.applies_to] = row

    return config


def _assert_acyclic_subtotals(by_name: dict[str, PnLLayoutRow]) -> None:
    visiting: set[str] = set()
    done: set[str] = set()

    def visit(name: str) -> None:
        if name in done:
            return
        if name in visiting:
            raise ConfigError(f"Cyclic subtotal dependency involving {name!r}.")
        visiting.add(name)
        row = by_name[name]
        if row.line_type is LineType.SUBTOTAL:
            for comp in row.components:
                visit(comp)
        elif row.line_type is LineType.MARGIN:
            for ref in (row.margin_numerator, row.margin_base):
                if ref is not None:
                    visit(ref)
        visiting.discard(name)
        done.add(name)

    for name in by_name:
        visit(name)


def _assert_business_hierarchy(rows: list[BusinessUnitRow]) -> None:
    units = {row.business_unit for row in rows}
    parent_of = {row.business_unit: row.parent for row in rows}
    for unit, parent in parent_of.items():
        if parent is not None and parent not in units:
            raise ConfigError(f"Business unit {unit!r} has unknown parent {parent!r}.")
    # Acyclic check.
    for start in units:
        seen: set[str] = set()
        cur: Optional[str] = start
        while cur is not None:
            if cur in seen:
                raise ConfigError(f"Cyclic business-unit hierarchy involving {start!r}.")
            seen.add(cur)
            cur = parent_of.get(cur)
