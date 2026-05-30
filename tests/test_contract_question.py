"""US2 contract test: Question schema + grounding."""

from __future__ import annotations

import json

import jsonschema

from agent.fakes import FakeLLMProvider, final, tool_call
from agent.investigate import investigate
from agent.models import RecordStatus
from tests.conftest import ROOT

SCHEMA = ROOT / "specs" / "002-ai-investigation-commentary" / "contracts" / "question.schema.json"


def _question_record(flag, result6, gl_tool6, settings, audit):
    provider = FakeLLMProvider([
        tool_call("query_gl_detail", {"reporting_line": flag.reporting_line, "period": 6, "scenario": "current_year"}),
        final({
            "status": "question",
            "hypothesis_text": "A late-booked supplier invoice may be the driver.",
            "hypothesis_row_ids": [],
            "narrative": "EBITDA differs by {{fig:flag.abs_variance}}. Is a late booking the cause?",
            "aggregates": [],
        }),
    ])
    return investigate(flag, result6, provider=provider, gl_tool=gl_tool6,
                       settings=settings, audit=audit, now="t")


def test_question_validates_against_schema(ebitda_flag, result6, gl_tool6, agent_settings, audit):
    record = _question_record(ebitda_flag, result6, gl_tool6, agent_settings, audit)
    assert record.status is RecordStatus.QUESTION
    schema = json.loads(SCHEMA.read_text())
    jsonschema.Draft202012Validator(schema).validate(record.question.model_dump(mode="json"))


def test_question_references_evidence_and_links_log(ebitda_flag, result6, gl_tool6, agent_settings, audit):
    record = _question_record(ebitda_flag, result6, gl_tool6, agent_settings, audit)
    assert record.question.evidence  # at least one embedded evidence row
    assert record.question.llm_log_refs
    assert record.question.text and "?" in record.question.text


def test_model_fields_match_schema(ebitda_flag):
    from agent.models import Question
    schema = json.loads(SCHEMA.read_text())
    assert set(Question.model_fields) == set(schema["properties"])
