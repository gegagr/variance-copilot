"""US4 contract test: FlaggedVariance public schema (FR-017)."""

from __future__ import annotations

import json

import jsonschema

from engine.models import FlaggedVariance
from tests.conftest import ROOT

SCHEMA_PATH = ROOT / "specs" / "001-pnl-variance-engine" / "contracts" / "flagged_variance.schema.json"


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_model_fields_match_schema_properties():
    """Drift guard: the model's fields must equal the committed schema's properties."""
    schema = _schema()
    assert set(FlaggedVariance.model_fields) == set(schema["properties"])


def test_serialized_flags_validate_against_schema(flags6):
    schema = _schema()
    validator = jsonschema.Draft202012Validator(schema)
    assert flags6
    for f in flags6:
        payload = f.model_dump(mode="json")
        validator.validate(payload)  # raises on mismatch


def test_decimals_serialize_as_strings(flags6):
    payload = flags6[0].model_dump(mode="json")
    assert isinstance(payload["current_value"], str)
    assert isinstance(payload["abs_threshold"], str)
    # Optional decimals are either string or null.
    assert payload["pp_variance"] is None or isinstance(payload["pp_variance"], str)


def test_schema_version_pinned(flags6):
    assert all(f.model_dump(mode="json")["schema_version"] == "1.0.0" for f in flags6)
