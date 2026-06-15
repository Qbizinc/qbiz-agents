"""Component 5 — Cost & Compute Governors.

Hard limits enforced in code, across two dimensions:

- **Cost limits** — token budget and USD spend. The token check fires *before* an API call
  (from an estimate); the spend check fires *after* (from actual usage).
- **Action limits** — counts of consequential operations: records touched, messages sent, tool
  calls made. This is how the *blast radius* — not just the bill — is bounded. A spend cap stops
  runaway cost; an action cap stops a cheap-but-destructive loop (the agent that sends 500 Slack
  messages while well under the token budget).

The governor also carries a **kill switch** (a hard global stop independent of any single limit)
and **redundancy detection** (refusing work it has already done this run).

This module is pure enforcement: it raises `BudgetExceededError` and holds no I/O. The call site
catches the rejection and records it through the audit log.
"""

from __future__ import annotations

from qbiz_harness.exceptions import BudgetExceededError


class CostGovernor:
    """Tracks spend, tokens, and consequential-action counts against hard caps.

    Every limit is checked in code, so no amount of model reasoning can exceed it. The check
    methods raise `BudgetExceededError` the moment a cap would be crossed — *before* the action
    they guard runs, so the limit bounds what actually happens, not just what gets billed.
    """

    def __init__(
        self,
        token_limit: int,
        spend_limit_usd: float,
        action_limits: dict[str, int] | None = None,
    ) -> None:
        self.token_limit = token_limit
        self.spend_limit = spend_limit_usd
        self.action_limits = dict(action_limits or {})

        self.tokens_used = 0
        self.spend_usd = 0.0
        self.action_counts: dict[str, int] = {}
        self._done_signatures: set[str] = set()
        self._killed = False

    # --- cost dimension -------------------------------------------------------------------

    def pre_call(self, estimated_tokens: int) -> None:
        """Guard an LLM call before it is made. Raises if the kill switch is engaged or the
        estimated token spend would breach the budget."""
        self._check_kill_switch()
        if self.tokens_used + estimated_tokens > self.token_limit:
            raise BudgetExceededError(
                f"Token limit reached: {self.tokens_used} + {estimated_tokens} "
                f"would exceed {self.token_limit}"
            )

    def post_call(self, tokens_used: int, cost_usd: float) -> None:
        """Record actual usage after a call. Raises if the spend cap is now breached."""
        self.tokens_used += tokens_used
        self.spend_usd += cost_usd
        if self.spend_usd > self.spend_limit:
            raise BudgetExceededError(
                f"Spend limit ${self.spend_limit:.2f} exceeded (now ${self.spend_usd:.2f})"
            )

    # --- action dimension -----------------------------------------------------------------

    def record_action(self, kind: str, count: int = 1) -> None:
        """Guard a consequential action (send, write, touch) before it runs. Raises if the kill
        switch is engaged or this action would push the count past its cap."""
        self._check_kill_switch()
        projected = self.action_counts.get(kind, 0) + count
        limit = self.action_limits.get(kind)
        if limit is not None and projected > limit:
            raise BudgetExceededError(
                f"Action limit for {kind!r} reached ({limit}); attempted to reach {projected}"
            )
        self.action_counts[kind] = projected

    # --- redundancy detection -------------------------------------------------------------

    def guard_redundant(self, signature: str) -> None:
        """Refuse work already done this run. `signature` identifies the unit of work (e.g. a
        normalized request hash). Raises if it has been seen; otherwise marks it done."""
        if signature in self._done_signatures:
            raise BudgetExceededError(f"Redundant work refused: {signature!r} already done this run")
        self._done_signatures.add(signature)

    # --- kill switch ----------------------------------------------------------------------

    def kill(self) -> None:
        """Engage the global stop. Every subsequent guarded call raises until a new run."""
        self._killed = True

    @property
    def killed(self) -> bool:
        return self._killed

    def _check_kill_switch(self) -> None:
        if self._killed:
            raise BudgetExceededError("Kill switch engaged — all further action halted")
