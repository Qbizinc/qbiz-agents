"""qbiz_harness — code-enforced limits for Qbiz agents.

A harness enforces what an agent is *allowed* to do, regardless of what it reasons.
Instructions are a request; the harness is enforcement. See HARNESS_PLAN.md.

This package depends on nothing in `agents/` or `mcp/`. The dependency direction is one-way:
agents import `qbiz_harness`; the harness imports nothing back.
"""

from qbiz_harness.audit import (
    AuditEvent,
    AuditLog,
    EventType,
    Intervention,
    InterventionLabel,
)
from qbiz_harness.cost_governor import CostGovernor
from qbiz_harness.exceptions import (
    BudgetExceededError,
    HarnessError,
    HitlEscalationRequired,
    InputRejectedError,
    LoopLimitError,
    ModelPolicyError,
    OutputRejectedError,
    PermissionDeniedError,
    RateLimitError,
)
from qbiz_harness.hitl import (
    ApprovalDecision,
    ApprovalTransport,
    TimeoutPolicy,
    hitl_checkpoint,
)
from qbiz_harness.model_policy import ActivityBand, ModelPolicy, Tier
from qbiz_harness.orchestration import LoopGuard, with_retry
from qbiz_harness.output_validator import (
    ValidationResult,
    Violation,
    check_format,
    check_scope,
    check_tool_calls,
    inspect_output,
    validate_output,
)

__version__ = "0.1.0"

__all__ = [
    # Exceptions
    "HarnessError",
    "InputRejectedError",
    "OutputRejectedError",
    "RateLimitError",
    "BudgetExceededError",
    "LoopLimitError",
    "PermissionDeniedError",
    "HitlEscalationRequired",
    "ModelPolicyError",
    # Component 5 — Cost & Compute Governors
    "CostGovernor",
    # Component 5 extension — Model-Tier Policy
    "ModelPolicy",
    "ActivityBand",
    "Tier",
    # Component 2 — Output Validator
    "validate_output",
    "inspect_output",
    "check_format",
    "check_tool_calls",
    "check_scope",
    "ValidationResult",
    "Violation",
    # Component 6 — Orchestration Controls
    "LoopGuard",
    "with_retry",
    # Component 8 — Human Checkpoints (HITL)
    "hitl_checkpoint",
    "ApprovalDecision",
    "ApprovalTransport",
    "TimeoutPolicy",
    # Cross-cutting — Audit Log
    "AuditLog",
    "AuditEvent",
    "EventType",
    "Intervention",
    "InterventionLabel",
    "__version__",
]
