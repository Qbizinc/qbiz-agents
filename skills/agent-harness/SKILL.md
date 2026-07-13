---
name: agent-harness
description: Wrap a Qbiz agent's consequential actions in the qbiz_harness package's code-enforced controls — cost/action caps, output validation, loop/retry guards, HITL approval gates, and an audit trail. Use whenever you are building, extending, or reviewing an agent or tool in this repo that spends tokens/money, calls tools, or takes an irreversible action. Requires the qbiz-agent-harness package (no MCP server).
roles:
  - consultant
  - data-engineer
  - platform-engineer
requires_mcp: []
---

# Agent Harness — Code-Enforced Limits

This skill covers `qbiz_harness` (`harness/` in this repo): the package that enforces what an
agent is **allowed** to do, independent of what it reasons its way into. Instructions to the model
are a request; the harness is enforcement. It is **not an MCP server** — it's a Python package you
import and call directly at the points in your agent where a consequential action happens.

The harness is **à la carte**: five independent controls you assemble at your agent's call site.
There is no turnkey "wrap my agent" function and no `limits.yaml` loader yet — you construct each
control in Python and call it where it matters. This is a few lines per agent, not a framework to
learn.

## When to use this skill

- You are **building a new agent or tool** in this repo that does any of: spends LLM tokens/money,
  sends messages, writes/deletes records, calls an external API, or loops on its own output.
- You are **reviewing** an existing agent and checking whether its consequential actions are
  actually capped, validated, and logged — or just trusted to the model's judgment.
- You need a **human approval gate** before an irreversible action (a production write, a ticket
  filed on someone's behalf, a rollback).
- You're deciding **what's safe to skip** — the harness only constrains what you explicitly wire
  up; unwired actions are unlimited.

## Available controls

| Control | Import | Use it to |
|---|---|---|
| Cost & action caps | `CostGovernor` | Cap tokens, USD spend, and per-action-kind counts (e.g. `messages_sent`, `records_touched`); kill switch; refuse redundant work. |
| Output validation | `validate_output` / `inspect_output` | Check the model's output shape, block hallucinated/out-of-allowlist tool calls, flag out-of-scope systems. `validate_output` raises (reject-and-re-prompt); `inspect_output` returns violations (strip-and-log). |
| Loop & retry control | `LoopGuard`, `with_retry` | Bound reasoning-loop iterations; give async steps bounded retries with backoff and a per-call timeout. |
| Human approval (HITL) | `hitl_checkpoint` | Block on a human's ✅/❌ before an irreversible action. Needs an `ApprovalTransport` — the [slack-bot-setup](../slack-bot-setup/SKILL.md) skill's `request_approval` provides one. |
| Audit log | `AuditLog` | Record every action and every intervention, local JSONL today; query the trail. |

Every `HarnessError` subclass (`BudgetExceededError`, `OutputRejectedError`, `LoopLimitError`,
`HitlEscalationRequired`, …) is raised by these controls when a limit fires. Your call site catches
it, logs it as an intervention, and routes to a fallback — re-prompt, escalate, or halt.

## Install & import

Add `qbiz-agent-harness` (the `harness/` package) as a dependency of your agent, then:

```python
from qbiz_harness import (
    CostGovernor,
    LoopGuard,
    AuditLog,
    validate_output,
    OutputRejectedError,
    BudgetExceededError,
    hitl_checkpoint,
    TimeoutPolicy,
)
```

See [SETUP.md](SETUP.md) for adding the dependency to a new agent's `pyproject.toml`.

## Core pattern: construct once, guard every consequential step

```python
AGENT_ID = "incident-agent"
ALLOWED_TOOLS = {"send_message", "add_reaction"}  # the agent's tool allowlist

audit = AuditLog(path="audit.jsonl")
governor = CostGovernor(
    token_limit=200_000,
    spend_limit_usd=5.00,
    action_limits={"messages_sent": 20},  # only what you choose to cap; everything else is unlimited
)
loop = LoopGuard(max_iterations=10)

def handle_step(model_output: dict, requested_tools: list[str]) -> None:
    loop.tick()  # raises LoopLimitError if the agent loops too long

    try:
        validate_output(
            model_output,
            expected_schema={"summary": str},
            requested_tools=requested_tools,
            allowed_tools=ALLOWED_TOOLS,
        )
    except OutputRejectedError as exc:
        audit.record_intervention(
            agent_id=AGENT_ID, action="validate_output",
            component="output_validator", prevented=str(exc),
        )
        return  # re-prompt or skip — your call

    try:
        governor.record_action("messages_sent")
    except BudgetExceededError as exc:
        audit.record_intervention(
            agent_id=AGENT_ID, action="send_message",
            component="cost_governor", prevented=str(exc),
        )
        return

    send_the_message(...)  # your tool call
    audit.record(agent_id=AGENT_ID, action="send_message", decision="allowed")
```

For an irreversible action, gate it behind a human first:

```python
decision = await hitl_checkpoint(
    transport,                      # e.g. the Slack MCP's request_approval
    channel="qbiz_slackbot_testing",
    prompt="Approve production rollback for job X? ✅/❌",
    timeout_policy=TimeoutPolicy.FAIL_CLOSED,  # no response → do not proceed (default; required for HIGH+ risk tier)
)
audit.record(agent_id=AGENT_ID, action="rollback", decision=decision.decision, user=decision.user)
if decision:            # truthy only if approved
    do_the_rollback()
```

## Recording interventions for fleet monitoring

When agents run across many jobs, always log a fired control with
`audit.record_intervention(...)`, passing `incident_id`, `cohort`, and `job_id`. That is what
powers the "did the agent handle it, or did the harness step in?" view —
`audit.intervention_counts()` gives the per-component tally, `audit.by_incident(id)` reconstructs
one incident's story. See `harness/HARNESS_PLAN.md` § Fleet Operation.

## Limits are per-agent, not baked in

- **Per-action-kind, not one global number.** `action_limits` is a dict, e.g.
  `{"messages_sent": 20, "records_touched": 1000, "tickets_created": 5}`. Cap what's irreversible;
  leave cheap reads unlimited.
- **Unlimited unless you say otherwise.** Any action kind not in the dict is never capped.
- **No default cap ships in code.** The right number is application-specific — a wrong default
  would be a false sense of safety. Pick it per agent, and expect to defend the number.
- Today you construct the governor in Python (as the pattern above does); there is no
  `limits.yaml` → `CostGovernor` loader yet.

## What's not ready yet

Don't reach for these — they're designed in `harness/HARNESS_PLAN.md` but not built, or blocked on
an open decision:

- **A turnkey agent wrapper / config loader.** Assemble controls at the call site, as above.
- **Input wrapper** (PII stripping, injection screening, rate limiting) — next up, not yet built.
- **Tool-level access controls** — blocked on the agent-identity decision `[D1]`.
- **Memory scoping** — only relevant if agents share a memory backend `[D2]`.
- **Evaluator agent** (LLM-based semantic checks) — blocked on the LLM-provider decision `[D3]`.
  `validate_output`/`inspect_output` today are mechanical checks only; don't ask them to catch
  factual errors or subtle semantic drift — that's this component's job, once it exists.
- **Production audit backend** (warehouse/SQL) — audit is local JSONL only today.

If you need one of these for a client engagement, say so explicitly rather than approximating it —
check `harness/README.md`'s "What's not ready yet" section for current status before assuming.

## Rules

- **One-way dependency:** agents import `qbiz_harness`; never import from `agents/` or `mcp/` into
  the harness itself.
- **Never fabricate a limit.** If you don't know an agent's token/spend/action caps, ask, or use
  the smallest sane placeholder and flag it clearly as unconfirmed — don't silently pick a
  "reasonable-sounding" number and move on.
- **Every intervention is audited.** A caught `HarnessError` that isn't logged via
  `audit.record_intervention(...)` is invisible to fleet monitoring — always log it, especially
  rejections.
- **Never work around a `HarnessError`.** Catching one and retrying the same action, loosening the
  limit inline, or suppressing it to "make the agent proceed anyway" defeats the entire point of
  the harness. The only valid responses are: re-prompt, escalate, or halt.
- **HITL decisions are binding.** Only proceed on an approved `hitl_checkpoint` result; on
  rejection or timeout, stop and report — see [slack-bot-setup](../slack-bot-setup/SKILL.md) for
  the same rule on the transport side.
- Classify the agent's risk tier (LOW–VERY HIGH, see `harness/HARNESS_PLAN.md`) before deciding
  whether HITL is required — HIGH+ actions default to `TimeoutPolicy.FAIL_CLOSED`.
