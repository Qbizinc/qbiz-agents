"""Gate 1 — cross-cutting Audit Log.

Covers the plan's "audit logging validation — confirm every action type produces a log entry"
and that the on-disk form is append-only, queryable JSONL.
"""

import json

from qbiz_harness import AuditLog, EventType, Intervention


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


# --- Fleet tagging: in-band vs. intervention, incident correlation, attribution ---


def test_plain_record_defaults_to_in_band_agent_action():
    log = AuditLog()
    event = log.record(agent_id="a", action="send_message", decision="allowed")

    assert event.event_type is EventType.AGENT_ACTION
    assert event.intervention is None
    assert event.incident_id is None and event.cohort is None and event.job_id is None


def test_record_intervention_stamps_type_and_detail():
    log = AuditLog()
    event = log.record_intervention(
        agent_id="finance-HIGH",
        action="send_message",
        component="cost_governor",
        prevented="capped messages_sent at 20",
        incident_id="inc-42",
        cohort="finance-HIGH",
        job_id="dag_invoice_reconcile",
    )

    assert event.event_type is EventType.HARNESS_INTERVENTION
    assert event.decision == "denied"
    assert event.intervention == Intervention(
        component="cost_governor", prevented="capped messages_sent at 20"
    )
    assert log.interventions() == [event]


def test_by_incident_reconstructs_the_story_in_order():
    log = AuditLog()
    log.record(agent_id="finance-HIGH", action="diagnose", decision="allowed", incident_id="inc-1")
    log.record_intervention(
        agent_id="finance-HIGH", action="send_message", component="cost_governor",
        prevented="capped messages_sent at 20", incident_id="inc-1",
    )
    log.record(agent_id="other", action="noise", decision="allowed", incident_id="inc-2")

    story = log.by_incident("inc-1")
    assert [e.action for e in story] == ["diagnose", "send_message"]


def test_intervention_counts_power_the_fleet_dashboard():
    log = AuditLog()
    log.record_intervention(agent_id="a", action="x", component="cost_governor", prevented="cap")
    log.record_intervention(agent_id="a", action="y", component="cost_governor", prevented="cap")
    log.record_intervention(agent_id="a", action="z", component="loop_guard", prevented="halt")
    log.record(agent_id="a", action="ok", decision="allowed")  # in-band, not counted

    assert log.intervention_counts() == {"cost_governor": 2, "loop_guard": 1}


def test_fleet_fields_serialize_to_jsonl(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path=path)
    log.record_intervention(
        agent_id="finance-HIGH", action="send_message", component="cost_governor",
        prevented="capped messages_sent at 20", incident_id="inc-7",
        cohort="finance-HIGH", job_id="dag_x",
    )

    parsed = json.loads(path.read_text(encoding="utf-8").strip())
    assert parsed["event_type"] == "harness_intervention"
    assert parsed["intervention"]["component"] == "cost_governor"
    assert parsed["intervention"]["prevented"] == "capped messages_sent at 20"
    assert parsed["intervention"]["label"] is None
    assert parsed["incident_id"] == "inc-7"
    assert parsed["cohort"] == "finance-HIGH"
    assert parsed["job_id"] == "dag_x"
