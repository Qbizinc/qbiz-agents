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
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class AuditEvent:
    """One structured, append-only record of something an agent attempted.

    The schema mirrors the plan's `{agent_id, action, inputs, outputs, ts, user, decision}`.
    `decision` is the harness verdict — "allowed", "denied", or a HITL outcome like "approved".
    """

    agent_id: str
    action: str
    decision: str
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    user: str | None = None
    reason: str | None = None
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
    ) -> AuditEvent:
        """Append one event. Returns it so the caller can reference what was logged."""
        event = AuditEvent(
            agent_id=agent_id,
            action=action,
            decision=decision,
            inputs=inputs or {},
            outputs=outputs or {},
            user=user,
            reason=reason,
        )
        self._events.append(event)
        if self._path is not None:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(event.to_json() + "\n")
        return event

    @property
    def events(self) -> list[AuditEvent]:
        """Every event recorded this run, in order. A copy — the log stays append-only."""
        return list(self._events)

    def by_decision(self, decision: str) -> list[AuditEvent]:
        """All events with a given verdict — e.g. every `denied` action, for forensics."""
        return [event for event in self._events if event.decision == decision]
