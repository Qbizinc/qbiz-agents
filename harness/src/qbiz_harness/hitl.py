"""Component 8 — Human Checkpoints (HITL).

A mandatory pause before a consequential action. The agent posts a yes/no prompt and blocks
until a human approves or rejects it, then proceeds or halts on that verdict. This is the layer
that neither rules (Layer 1) nor an evaluator (Layer 2) can replace — the irreducible human
judgment in front of an irreversible action.

Two design rules, both from the plan:

- **The harness imports nothing from the MCP/agent side** (Decision Locked #3). This module does
  not import the Slack MCP. It defines an `ApprovalTransport` protocol — the small async surface a
  checkpoint needs — and the call site injects a Slack-backed implementation. The protocol mirrors
  the Slack MCP's `request_approval(channel, prompt, timeout_seconds, thread_ts)` tool, which posts
  the prompt *and* blocks for the reaction, so a checkpoint is one transport call, not a separate
  post-then-wait.
- **The timeout policy is per-agent** (decision ``[D6]``): fail-closed, fail-open, or escalate.
  It defaults to **fail-closed** — the safe default the plan mandates for HIGH+ agents — so a
  silent timeout never lets an action through by accident.

Like the other enforcement components, this stays pure of audit I/O: it returns a structured
`ApprovalDecision` and the call site records it through `AuditLog`. See `audit.py` for why the
components log through the call site rather than reaching for the log themselves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from qbiz_harness.exceptions import HitlEscalationRequired


class TimeoutPolicy(Enum):
    """What a checkpoint does when no human responds before the timeout — decision ``[D6]``.

    Per-agent config, not a property of the mechanism. ``FAIL_CLOSED`` is the default and the
    mandated choice for HIGH+ agents.
    """

    FAIL_CLOSED = "fail_closed"  # no response → do not proceed (safest)
    FAIL_OPEN = "fail_open"  # no response → proceed after timeout (LOW risk, time-sensitive only)
    ESCALATE = "escalate"  # no response → raise HitlEscalationRequired; page a secondary contact


@runtime_checkable
class ApprovalTransport(Protocol):
    """The async surface a checkpoint needs from whatever channel carries the approval.

    Implemented by the Slack MCP's `request_approval` tool, but deliberately abstract so the
    harness never depends on Slack. Any transport that can post a prompt, block for a human, and
    return `{decision, user, ...}` satisfies it.
    """

    async def request_approval(
        self,
        *,
        channel: str,
        prompt: str,
        timeout_seconds: int,
        thread_ts: str | None = None,
    ) -> dict[str, Any]:
        """Post `prompt` to `channel`, block until a human responds or `timeout_seconds` elapses.

        Returns at least `{"decision": "approved" | "rejected" | "timed_out", "user": str | None}`.
        Extra keys (e.g. `ts`, `reaction`) are preserved on the result for the audit trail.
        """
        ...


@dataclass(slots=True)
class ApprovalDecision:
    """The outcome of one checkpoint, structured for the audit trail.

    Truthy iff the agent may proceed, so a call site can write `if await hitl_checkpoint(...):`.
    A timeout is truthy only under the fail-open policy.
    """

    decision: str  # "approved" | "rejected" | "timed_out"
    approved: bool
    policy: TimeoutPolicy
    timed_out: bool
    user: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.approved


async def hitl_checkpoint(
    transport: ApprovalTransport,
    *,
    channel: str,
    prompt: str,
    timeout_seconds: int = 120,
    timeout_policy: TimeoutPolicy = TimeoutPolicy.FAIL_CLOSED,
    thread_ts: str | None = None,
) -> ApprovalDecision:
    """Block on a human approval before a consequential action; return the structured verdict.

    A clear `approved`/`rejected` from the human is honoured as-is regardless of policy. Only a
    *timeout* consults `timeout_policy`:
    - `FAIL_CLOSED` → not approved (the action does not proceed)
    - `FAIL_OPEN`   → approved (proceed; reserve for LOW-risk, time-sensitive actions)
    - `ESCALATE`    → raise `HitlEscalationRequired` so orchestration can page a secondary contact

    An unrecognised `decision` from the transport is treated as a timeout — the conservative read,
    so a malformed response can never silently approve under fail-closed.

    The caller is expected to record the returned `ApprovalDecision` through `AuditLog` (who
    approved, what they saw, when). This function performs no audit I/O itself.
    """
    raw = await transport.request_approval(
        channel=channel,
        prompt=prompt,
        timeout_seconds=timeout_seconds,
        thread_ts=thread_ts,
    )
    decision = raw.get("decision")
    user = raw.get("user")

    if decision == "approved":
        return ApprovalDecision(
            decision="approved",
            approved=True,
            policy=timeout_policy,
            timed_out=False,
            user=user,
            raw=raw,
        )
    if decision == "rejected":
        return ApprovalDecision(
            decision="rejected",
            approved=False,
            policy=timeout_policy,
            timed_out=False,
            user=user,
            raw=raw,
        )

    # Timed out, or an unrecognised verdict treated as one. Policy decides.
    if timeout_policy is TimeoutPolicy.ESCALATE:
        raise HitlEscalationRequired(
            f"HITL checkpoint in {channel!r} timed out after {timeout_seconds}s with no response "
            f"— escalating per policy."
        )
    return ApprovalDecision(
        decision="timed_out",
        approved=timeout_policy is TimeoutPolicy.FAIL_OPEN,
        policy=timeout_policy,
        timed_out=True,
        user=None,
        raw=raw,
    )
