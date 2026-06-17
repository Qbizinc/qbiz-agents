"""Exception hierarchy for the harness.

Every component raises a subclass of `HarnessError`, so a caller can catch the whole harness
boundary with one `except HarnessError` while still being able to distinguish *why* enforcement
fired. This module is decision-independent — it stands regardless of how agent identity, memory,
or model routing get settled later.
"""

from __future__ import annotations


class HarnessError(Exception):
    """Base class for every limit the harness enforces.

    Catching this catches any harness-initiated rejection. Subclasses identify which layer fired.
    """


class InputRejectedError(HarnessError):
    """Component 1 — input failed screening (prompt injection, schema, PII) before the LLM call."""


class OutputRejectedError(HarnessError):
    """Component 2 — LLM output failed validation (bad format, hallucinated tool, out of scope)."""


class RateLimitError(HarnessError):
    """Component 1 — the agent exceeded its allowed call rate."""


class BudgetExceededError(HarnessError):
    """Component 5 — a token or spend cap was reached."""


class LoopLimitError(HarnessError):
    """Component 6 — the agent exceeded its iteration budget; escalate to a human."""


class PermissionDeniedError(HarnessError):
    """Component 3 — the agent is not permitted to call this tool with these arguments."""


class HitlEscalationRequired(HarnessError):
    """Component 8 — a HITL checkpoint timed out under the *escalate* policy.

    Not a rejection: no human gave a verdict in time and the agent's policy is to neither
    proceed (fail-open) nor halt silently (fail-closed) but to page a secondary contact and
    pause. The orchestration layer catches this to route to that escalation path.
    """
