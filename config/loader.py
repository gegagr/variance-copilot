"""Format-agnostic config loader (imperative shell — performs I/O).

Today this reads CSV. The ``read_table`` indirection isolates the file format, so an
xlsx loader can be substituted later without touching the schemas or the engine. The
loader returns a fully-validated :class:`EngineConfig`; the engine never sees a file.
"""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path
from typing import Optional

from config.schemas import (
    BusinessUnitRow,
    CoaMappingRow,
    ConfigError,
    EngineConfig,
    EntityGeographyRow,
    PnLLayoutRow,
    ReportingSettings,
    ThresholdRow,
    validate_config,
)
from engine.models import LineType

COMPONENT_SEP = ";"


def read_table(path: Path) -> list[dict[str, str]]:
    """Read a tabular file into a list of string-valued row dicts.

    The single point that knows the on-disk format. Swap this for an xlsx reader to
    support xlsx config without changing anything else.
    """
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]


def _opt(value: str) -> Optional[str]:
    return value if value else None


def load_config(config_dir: Path, current_period: Optional[int] = None) -> EngineConfig:
    """Load and validate all config files from ``config_dir``.

    ``current_period`` (if provided) overrides the value in reporting_settings.csv.
    """
    config_dir = Path(config_dir)

    coa = [
        CoaMappingRow(gl_account=r["gl_account"], reporting_line=r["reporting_line"])
        for r in read_table(config_dir / "coa_mapping.csv")
    ]
    business = [
        BusinessUnitRow(business_unit=r["business_unit"], parent=_opt(r.get("parent", "")))
        for r in read_table(config_dir / "business_structure.csv")
    ]
    entities = [
        EntityGeographyRow(entity=r["entity"], geography=r["geography"], rollup=r["rollup"])
        for r in read_table(config_dir / "entities_geographies.csv")
    ]
    layout = [
        PnLLayoutRow(
            reporting_line=r["reporting_line"],
            order=int(r["order"]),
            line_type=LineType(r["line_type"]),
            components=[c for c in r.get("components", "").split(COMPONENT_SEP) if c],
            margin_numerator=_opt(r.get("margin_numerator", "")),
            margin_base=_opt(r.get("margin_base", "")),
        )
        for r in read_table(config_dir / "pnl_layout.csv")
    ]
    thresholds = [
        ThresholdRow(
            rule_id=r["rule_id"],
            applies_to=r["applies_to"],
            abs_threshold=Decimal(r["abs_threshold"]),
            pct_threshold=Decimal(r["pct_threshold"]),
            pp_threshold=Decimal(r["pp_threshold"]),
        )
        for r in read_table(config_dir / "thresholds.csv")
    ]

    settings = _load_settings(config_dir / "reporting_settings.csv")
    if current_period is not None:
        settings = settings.model_copy(update={"current_period": current_period})
    if not 1 <= settings.current_period <= 12:
        raise ConfigError(f"current_period must be 1..12, got {settings.current_period}.")

    config = EngineConfig(
        coa=coa,
        business=business,
        entities=entities,
        layout=layout,
        thresholds=thresholds,
        settings=settings,
    )
    return validate_config(config)


def _load_settings(path: Path) -> ReportingSettings:
    rows = read_table(path)
    if not rows:
        return ReportingSettings()
    r = rows[0]
    return ReportingSettings(
        reporting_currency=r.get("reporting_currency", "EUR"),
        money_precision=int(r.get("money_precision", "2")),
        ratio_precision=int(r.get("ratio_precision", "6")),
        current_period=int(r.get("current_period", "12")),
        not_meaningful_label=r.get("not_meaningful_label", "n/m"),
        sign_convention=r.get("sign_convention", "natural_signed"),
    )
