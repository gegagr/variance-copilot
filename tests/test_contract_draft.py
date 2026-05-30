"""US3 contract test: Draft schema + provenance + is_proposal."""

from __future__ import annotations

import json

import jsonschema

from agent.fakes import FakeLLMProvider, final, tool_call
from agent.investigate import investigate
from agent.models import Draft, RecordStatus
from tests.conftest import ROOT

SCHEMA = ROOT / "specs" / "002-ai-investigation-commentary" / "contracts" / "draft.schema.json"


def test_self_explanatory_draft_validates(ebitda_flag, result6, gl_tool6, agent_settings, audit):
    provider = FakeLLMProvider([
        tool_call("query_gl_detail", {"reporting_line": ebitda_flag.reporting_line, "period": 6, "scenario": "current_year"}),
        final({"status": "draft",
               "narrative": "EBITDA reached {{fig:flag.current_value}} versus {{fig:flag.comparator_value}}.",
               "aggregates": []}),
    ])
    record = investigate(ebitda_flag, result6, provider=provider, gl_tool=gl_tool6,
                         settings=agent_settings, audit=audit, now="t")
    assert record.status is RecordStatus.DRAFT
    draft = record.draft
    assert draft.is_proposal is True
    assert draft.controller_input is None  # self-explanatory, no question posed
    assert draft.provenance.flag_id == ebitda_flag.flag_id
    assert draft.provenance.evidence_row_ids

    schema = json.loads(SCHEMA.read_text())
    jsonschema.Draft202012Validator(schema).validate(draft.model_dump(mode="json"))


def test_model_fields_match_schema():
    schema = json.loads(SCHEMA.read_text())
    assert set(Draft.model_fields) == set(schema["properties"])
