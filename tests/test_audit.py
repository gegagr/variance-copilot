"""US4: audit log completeness + API key never written + output linkage."""

from __future__ import annotations

from agent.audit import AuditLog
from agent.fakes import FakeLLMProvider, final, tool_call
from agent.investigate import investigate


def test_entry_has_required_fields_and_redacts_key():
    log = AuditLog()
    eid = log.record(
        model="openrouter/auto",
        request={"messages": [{"role": "user", "content": "hi"}], "authorization": "Bearer sk-secret"},
        response={"ok": True},
        now="2026-05-30T00:00:00Z",
    )
    entry = log.entries[0]
    assert entry["entry_id"] == eid
    assert {"entry_id", "ts", "model", "request", "response", "tool_calls"} <= set(entry)
    assert entry["request"]["authorization"] == "***redacted***"
    assert "sk-secret" not in str(entry)


def test_every_call_logged_and_outputs_link(ebitda_flag, result6, gl_tool6, agent_settings, audit):
    provider = FakeLLMProvider([
        tool_call("query_gl_detail", {"reporting_line": ebitda_flag.reporting_line, "period": 6, "scenario": "current_year"}),
        final({"status": "draft", "narrative": "EBITDA at {{fig:flag.current_value}}.", "aggregates": []}),
    ])
    record = investigate(ebitda_flag, result6, provider=provider, gl_tool=gl_tool6,
                         settings=agent_settings, audit=audit, now="2026-05-30T00:00:00Z")
    # two model calls => two log entries; the output links to them.
    assert len(audit.entries) == 2
    assert record.draft.llm_log_refs == [e["entry_id"] for e in audit.entries]
    assert all(e["ts"] == "2026-05-30T00:00:00Z" for e in audit.entries)
