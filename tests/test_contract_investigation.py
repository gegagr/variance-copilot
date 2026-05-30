"""US1 contract test: InvestigationRecord schema + one-record-per-flag."""

from __future__ import annotations

import json

import jsonschema
from referencing import Registry, Resource

from agent.fakes import FakeLLMProvider, final, tool_call
from agent.investigate import investigate
from tests.conftest import ROOT

CONTRACTS = ROOT / "specs" / "002-ai-investigation-commentary" / "contracts"
SCHEMA = CONTRACTS / "investigation_record.schema.json"


def _validator():
    """A validator with the Question/Draft schemas registered so $ref by $id resolves."""
    main = json.loads(SCHEMA.read_text())
    resources = []
    for name in ("question.schema.json", "draft.schema.json"):
        doc = json.loads((CONTRACTS / name).read_text())
        resources.append((doc["$id"], Resource.from_contents(doc)))
    registry = Registry().with_resources(resources)
    return jsonschema.Draft202012Validator(main, registry=registry)


def test_investigation_record_validates(ebitda_flag, result6, gl_tool6, agent_settings, audit):
    provider = FakeLLMProvider([
        tool_call("query_gl_detail", {"reporting_line": ebitda_flag.reporting_line, "period": 6, "scenario": "current_year"}),
        final({"status": "draft", "narrative": "EBITDA reached {{fig:flag.current_value}}.", "aggregates": []}),
    ])
    record = investigate(ebitda_flag, result6, provider=provider, gl_tool=gl_tool6,
                         settings=agent_settings, audit=audit, now="t")
    payload = record.model_dump(mode="json")
    _validator().validate(payload)
    assert payload["status"] == "draft"
    assert payload["draft"] is not None and payload["question"] is None


def test_one_record_per_flag(flags6, result6, gl_tool6, agent_settings, audit):
    """Each flag investigated yields exactly one record (or None on fail-safe)."""
    records = []
    for flag in flags6[:3]:
        provider = FakeLLMProvider([
            final({"status": "question", "hypothesis_text": None,
                   "narrative": "Could not determine a driver. Please add context.", "aggregates": []}),
        ])
        rec = investigate(flag, result6, provider=provider, gl_tool=gl_tool6,
                          settings=agent_settings, audit=audit, now="t")
        records.append(rec)
    assert len(records) == 3
    assert all(r is not None and r.flag_id == f.flag_id for r, f in zip(records, flags6[:3]))
