"""Gate 1 — cross-cutting Audit Log.

Covers the plan's "audit logging validation — confirm every action type produces a log entry"
and that the on-disk form is append-only, queryable JSONL.
"""

import json

from qbiz_harness import AuditLog


def test_record_appends_in_order_and_returns_event():
    log = AuditLog()
    first = log.record(agent_id="incident-agent", action="send_message", decision="allowed")
    log.record(agent_id="incident-agent", action="create_ticket", decision="denied", reason="cap")

    assert [e.action for e in log.events] == ["send_message", "create_ticket"]
    assert first.decision == "allowed"


def test_by_decision_filters_for_forensics():
    log = AuditLog()
    log.record(agent_id="a", action="x", decision="allowed")
    log.record(agent_id="a", action="y", decision="denied", reason="action limit")
    log.record(agent_id="a", action="z", decision="denied", reason="kill switch")

    denied = log.by_decision("denied")
    assert {e.action for e in denied} == {"y", "z"}


def test_persists_as_jsonl_when_path_given(tmp_path):
    path = tmp_path / "nested" / "audit.jsonl"
    log = AuditLog(path=path)
    log.record(agent_id="incident-agent", action="send_message", decision="allowed",
               inputs={"channel": "qbiz_slackbot_testing"})
    log.record(agent_id="incident-agent", action="send_message", decision="denied",
               reason="action limit for 'messages_sent' reached (20)")

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2  # one JSON object per event, append-only
    parsed = json.loads(lines[0])
    assert parsed["agent_id"] == "incident-agent"
    assert parsed["inputs"]["channel"] == "qbiz_slackbot_testing"
    assert parsed["ts"]  # timestamp stamped automatically
