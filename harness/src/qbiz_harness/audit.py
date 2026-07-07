"""Cross-cutting audit log — a first-class record of every action the harness sees.

This is not one of the Vision's eight numbered components; it is the infrastructure they all
record through. The audit log answers the forensic question — "what did the agent do, when, and
what did the harness decide about it?" — for any HIGH+ agent.

Design choices for this stage:
- **Append-only.** Events are only ever added, never mutated. The demo writes newline-delimited
  JSON (JSONL) to a local file; the production storage backend (BigQuery / S3 object-lock) is
  decision ``[D4]`` in the plan and not needed yet. The JSONL writer is swappable without
  touching callers.
- **Components stay pure.** The enforcement components (cost governor, orchestration) raise
  exceptions and hold no I/O. The *call site* — the integration layer that wires the harness
  around an agent — records audit events, including the enforcement rejections it catches. This
  keeps the components dependency-free and unit-testable while still giving us a complete trail.
- **Fleet-ready schema.** Every event carries an ``event_type`` that separates *in-band agent
  actions* from *harness interventions* (and HITL / evaluator outcomes), plus an ``incident_id``
  that stitches one incident across watcher → reasoning → tool calls → interventions → HITL →
  resolution, and ``cohort`` / ``job_id`` for fleet attribution. This is what powers the
  "how often did the harness step in?" view — see HARNESS_PLAN.md § Fleet Operation. The fields
  are additive: a single-agent caller can ignore them entirely and get the original schema.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventType(str, Enum):
    """What kind of event this is — the in-band-vs-intervention split.

    A ``str`` enum so it serializes to its plain value in JSON and reads back as a string when
    queried over the audit table, no enum machinery required downstream.
    """

    AGENT_ACTION = "agent_action"  # in-band: the agent acted within its bounds
    HARNESS_INTERVENTION = "harness_intervention"  # a control fired and changed the outcome
    HITL_DECISION = "hitl_decision"  # a human approved/rejected/timed-out
    EVALUATOR_FLAG = "evaluator_flag"  # the evaluator (Component 7) raised a concern


class InterventionLabel(str, Enum):
    """Post-hoc verdict on an intervention — was it a real catch or a limit set too tight?

    Stamped later (human review, or the evaluator labels a sample), not at record time, so it
    defaults to ``None`` on the event. Feeds limit tuning; keeps "32 interventions" from reading
    as all-good or all-bad. See HARNESS_PLAN.md § Fleet Operation.
    """

    GOOD_CATCH = "good_catch"
    FALSE_POSITIVE = "false_positive"


@dataclass(slots=True)
class Intervention:
    """Detail of a harness intervention: which control fired and what it prevented.

    Present only on ``harness_intervention`` events. ``component`` is the firing component
    (e.g. ``"cost_governor"``, ``"loop_guard"``, ``"access_controls"``) so the dashboard can
    count "18 cost caps, 9 loop guards"; ``prevented`` is the human-readable thing it stopped
    (e.g. ``"capped messages_sent at 20"``).
    """

    component: str
    prevented: str
    label: InterventionLabel | None = None


@dataclass(slots=True)
class AuditEvent:
    """One structured, append-only record of something an agent attempted.

    The base schema mirrors the plan's `{agent_id, action, inputs, outputs, ts, user, decision}`.
    `decision` is the harness verdict — "allowed", "denied", or a HITL outcome like "approved".

    The fleet fields — `event_type`, `intervention`, `incident_id`, `cohort`, `job_id` — extend
    that for multi-agent monitoring (see HARNESS_PLAN.md § Fleet Operation). They are optional:
    `event_type` defaults to a plain in-band agent action and the rest to `None`, so a
    single-agent call site gets the original behaviour for free.
    """

    agent_id: str
    action: str
    decision: str
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    user: str | None = None
    reason: str | None = None
    event_type: EventType = EventType.AGENT_ACTION
    intervention: Intervention | None = None
    incident_id: str | None = None
    cohort: str | None = None
    job_id: str | None = None
    ts: str = field(default_factory=_utc_now_iso)

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str)


class AuditLog:
    """Append-only event sink. In-memory always; optionally mirrored to a JSONL file.

    Pass a `path` to persist (the demo does this so the trail survives the run and can be
    inspected). Without a path it is purely in-memory, which is what unit tests want.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self._events: list[AuditEvent] = []
        self._path = Path(path) if path is not None else None
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        *,
        agent_id: str,
        action: str,
        decision: str,
        inputs: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
        user: str | None = None,
        reason: str | None = None,
        event_type: EventType = EventType.AGENT_ACTION,
        intervention: Intervention | None = None,
        incident_id: str | None = None,
        cohort: str | None = None,
        job_id: str | None = None,
    ) -> AuditEvent:
        """Append one event. Returns it so the caller can reference what was logged.

        Fleet fields default to a plain in-band agent action; pass them to attribute the event
        to an incident/cohort/job. For interventions prefer :meth:`record_intervention`, which
        sets `event_type` and builds the `Intervention` for you.
        """
        event = AuditEvent(
            agent_id=agent_id,
            action=action,
            decision=decision,
            inputs=inputs or {},
            outputs=outputs or {},
            user=user,
            reason=reason,
            event_type=event_type,
            intervention=intervention,
            incident_id=incident_id,
            cohort=cohort,
            job_id=job_id,
        )
        self._append(event)
        return event

    def record_intervention(
        self,
        *,
        agent_id: str,
        action: str,
        component: str,
        prevented: str,
        inputs: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
        user: str | None = None,
        reason: str | None = None,
        incident_id: str | None = None,
        cohort: str | None = None,
        job_id: str | None = None,
        decision: str = "denied",
    ) -> AuditEvent:
        """Record a harness intervention — a control fired and changed the outcome.

        Stamps `event_type=harness_intervention` and attaches an `Intervention(component,
        prevented)`. This is the call site's natural home at the exception boundary: catch the
        component's `HarnessError`, then log here. `component`/`prevented` are what the fleet
        dashboard counts and explains ("18 cost caps, 9 loop guards").
        """
        return self.record(
            agent_id=agent_id,
            action=action,
            decision=decision,
            inputs=inputs,
            outputs=outputs,
            user=user,
            reason=reason,
            event_type=EventType.HARNESS_INTERVENTION,
            intervention=Intervention(component=component, prevented=prevented),
            incident_id=incident_id,
            cohort=cohort,
            job_id=job_id,
        )

    def _append(self, event: AuditEvent) -> None:
        self._events.append(event)
        if self._path is not None:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(event.to_json() + "\n")

    @property
    def events(self) -> list[AuditEvent]:
        """Every event recorded this run, in order. A copy — the log stays append-only."""
        return list(self._events)

    def by_decision(self, decision: str) -> list[AuditEvent]:
        """All events with a given verdict — e.g. every `denied` action, for forensics."""
        return [event for event in self._events if event.decision == decision]

    def by_event_type(self, event_type: EventType) -> list[AuditEvent]:
        """All events of one kind — e.g. every `harness_intervention`, for the fleet view."""
        return [event for event in self._events if event.event_type == event_type]

    def interventions(self) -> list[AuditEvent]:
        """Every event where a harness control fired. The numerator of the intervention rate."""
        return self.by_event_type(EventType.HARNESS_INTERVENTION)

    def by_incident(self, incident_id: str) -> list[AuditEvent]:
        """Every event for one incident, in order — the per-incident story, reconstructable."""
        return [event for event in self._events if event.incident_id == incident_id]

    def intervention_counts(self) -> dict[str, int]:
        """How many times each component intervened — drives "18 cost caps, 9 loop guards"."""
        counts: dict[str, int] = {}
        for event in self.interventions():
            if event.intervention is not None:
                key = event.intervention.component
                counts[key] = counts.get(key, 0) + 1
        return counts
