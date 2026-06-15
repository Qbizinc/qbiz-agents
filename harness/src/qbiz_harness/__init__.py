"""qbiz_harness — code-enforced limits for Qbiz agents.

A harness enforces what an agent is *allowed* to do, regardless of what it reasons.
Instructions are a request; the harness is enforcement. See HARNESS_PLAN.md.

This package depends on nothing in `agents/` or `mcp/`. The dependency direction is one-way:
agents import `qbiz_harness`; the harness imports nothing back.
"""

from qbiz_harness.audit import AuditEvent, AuditLog
from qbiz_harness.cost_governor import CostGovernor
from qbiz_harness.exceptions import (
    BudgetExceededError,
    HarnessError,
    InputRejectedError,
    LoopLimitError,
    OutputRejectedError,
    PermissionDeniedError,
    RateLimitError,
)
from qbiz_harness.orchestration import LoopGuard, with_retry

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
    # Component 5 — Cost & Compute Governors
    "CostGovernor",
    # Component 6 — Orchestration Controls
    "LoopGuard",
    "with_retry",
    # Cross-cutting — Audit Log
    "AuditLog",
    "AuditEvent",
    "__version__",
]
