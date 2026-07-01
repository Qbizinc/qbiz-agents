# qbiz-agent-harness

Code-enforced limits on what Qbiz agents are *allowed* to do, regardless of what they reason.
Instructions are a request; the harness is enforcement.

See [HARNESS_PLAN.md](HARNESS_PLAN.md) for the full design — the eight components, risk tiers,
and quality gates.

## Status

Phase 1 foundational components are in (the unblocked, decision-independent ones):

- `src/qbiz_harness/exceptions.py` — the `HarnessError` hierarchy every component raises through.
- `src/qbiz_harness/cost_governor.py` — **Component 5**: token/spend caps, action-count limits,
  kill switch, redundancy detection.
- `src/qbiz_harness/orchestration.py` — **Component 6**: bounded retry/backoff, per-call timeout,
  loop guard.
- `src/qbiz_harness/output_validator.py` — **Component 2**: mechanical output checks — format/schema
  validation, hallucinated-tool detection (against the per-agent allowlist shared with Component 3),
  and out-of-scope system flagging. Each check is opt-in at the call site. Two entry points realize
  the partial-output policy: `validate_output` raises (reject-and-re-prompt); `inspect_output`
  returns the violations (strip-and-log).
- `src/qbiz_harness/audit.py` — cross-cutting **append-only audit log** (local JSONL for now;
  production storage backend is decision `[D4]`). Carries the **fleet schema** — `event_type`
  (in-band agent action vs. harness intervention vs. HITL vs. evaluator flag), `intervention`
  detail, `incident_id`, `cohort`, `job_id` — with `record_intervention(...)` plus
  `interventions()` / `by_incident()` / `intervention_counts()` queries behind it. Fields are
  additive, so single-agent callers are unaffected. See HARNESS_PLAN.md § Fleet Operation.
- `src/qbiz_harness/hitl.py` — **Component 8**: human approval checkpoints. Wraps an injected
  approval transport (the Slack MCP's `request_approval`); per-agent timeout policy `[D6]`
  (fail-closed / fail-open / escalate), defaulting to fail-closed for HIGH+.

Still to come, per the plan's build order: input wrapper (Phase 2, unblocked — regex-only first,
`[D5]` picks a library later), then the decision-gated pieces — access controls (`[D1]`), memory
scoping (`[D2]`), evaluator (`[D3]`).

## Using the Harness (consultant guide)

This section is the practical how-to for putting the harness around an agent on a client
engagement. It is kept current as capabilities land — if something you need isn't here yet, it
isn't built yet (check [What's not ready yet](#whats-not-ready-yet) below).

**Where it stands today:** the harness is a set of **à la carte enforcement components you assemble
at your agent's call site** — not yet a one-line wrapper. There is no turnkey "wrap my agent" entry
point and no config-from-YAML loader yet; you construct each control in Python and call it at the
right point in your agent loop. The components are small and independent on purpose, so this is a
few lines, not a framework to learn.

The pattern is always the same: **construct the controls once, then guard each consequential step,
and log every verdict — especially the rejections — through the audit log.** The enforcement
components raise a `HarnessError` subclass when a limit fires; your call site catches it, records it
as an intervention, and routes to a fallback (re-prompt, escalate, or halt).

### What you can use today

| Control | Import | Use it to |
|---|---|---|
| **Cost & action caps** (Component 5) | `CostGovernor` | Cap tokens, USD spend, and per-action-kind counts (messages sent, records touched); kill switch; refuse redundant work. |
| **Output validation** (Component 2) | `validate_output` / `inspect_output` | Check the model's output shape, block hallucinated/out-of-allowlist tool calls, flag out-of-scope systems. |
| **Loop & retry control** (Component 6) | `LoopGuard`, `with_retry` | Bound reasoning-loop iterations; give async steps bounded retries with backoff and a per-call timeout. |
| **Human approval** (Component 8) | `hitl_checkpoint` | Block on a human ✅/❌ before an irreversible action. Needs an `ApprovalTransport` (the Slack MCP provides one). |
| **Audit log** (cross-cutting) | `AuditLog` | Record every action and every intervention; query the trail. Local JSONL today. |

### Install & import

The harness is the `qbiz_harness` package in this repo. From an agent in `qbiz-agents`, add it as a
dependency and import what you need:

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

### Minimal pattern: guard an agent step

Construct the controls once per run, then wrap each consequential step. This example caps cost and
messages, validates the model's output against the agent's tool allowlist, and logs both the action
and any intervention:

```python
AGENT_ID = "incident-agent"
ALLOWED_TOOLS = {"send_message", "add_reaction"}  # the per-agent allowlist (shared with Component 3)

audit = AuditLog(path="audit.jsonl")
governor = CostGovernor(
    token_limit=200_000,
    spend_limit_usd=5.00,
    action_limits={"messages_sent": 20},  # only what you choose to cap; everything else is unlimited
)
loop = LoopGuard(max_iterations=10)

def handle_step(model_output: dict, requested_tools: list[str]) -> None:
    loop.tick()  # raises LoopLimitError if the agent loops too long

    # 1. Validate the model's output before acting on it.
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

    # 2. Guard each consequential action against its cap, then do it.
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

For an irreversible action, gate it behind a human first (`hitl_checkpoint` is async; inject a
Slack-backed `ApprovalTransport`):

```python
decision = await hitl_checkpoint(
    transport,                      # e.g. the Slack MCP's request_approval
    channel="qbiz_slackbot_testing",
    prompt="Approve production rollback for job X? ✅/❌",
    timeout_policy=TimeoutPolicy.FAIL_CLOSED,  # no response → do not proceed (default; required for HIGH+)
)
audit.record(agent_id=AGENT_ID, action="rollback", decision=decision.decision, user=decision.user)
if decision:            # truthy only if approved
    do_the_rollback()
```

### Recording interventions for fleet monitoring

When you run agents across many jobs, always log a fired control with
`audit.record_intervention(...)` and pass `incident_id`, `cohort`, and `job_id`. That is what powers
the "did the agent handle it, or did the harness step in?" view and the intervention-rate metric —
`audit.intervention_counts()` gives the per-component tally, `audit.by_incident(id)` reconstructs one
incident's story. See [HARNESS_PLAN.md](HARNESS_PLAN.md) § Fleet Operation.

### What's not ready yet

Don't reach for these — they're tracked in the plan but not built (or are decision-gated):

- **A turnkey agent wrapper / config loader.** No `limits.yaml` → `CostGovernor` loader and no
  single call that wires all components. Assemble at the call site, as above.
- **Input wrapper** (Component 1) — PII stripping, injection screening, rate limiting. *Next up.*
- **Tool-level access controls** (Component 3) — blocked on the agent-identity decision `[D1]`.
- **Memory scoping** (Component 4) — only if agents share a memory backend `[D2]`.
- **Evaluator agent** (Component 7) — blocked on the LLM-provider decision `[D3]`.
- **Production audit backend** (warehouse / SQL) — `[D4]`; today the audit log is local JSONL only.
- **Fleet manifest & watcher tier** — design-led; see the plan's Fleet Operation section.

## Demo

A no-LLM walkthrough of the harness stopping a runaway agent — the plan's HIGH-tier *Agentic
Incident DAG* tries to spam Slack, loop forever, and file a ticket; the harness caps the messages
(Component 5), halts the loop (Component 6), makes a human reject the irreversible ticket
(Component 8, via a scripted approval transport — no real Slack), then a kill switch stops it cold.
Every verdict lands in the audit trail. Needs no API key (provider decision `[D3]` is still open).

```bash
uv run python demo/incident_runaway.py
```

### Are the limits configurable? (the question the demo will raise)

Yes — entirely, and per agent. Nothing is baked into the harness:

- **Per-action-kind, not one global number.** `action_limits` is a dict, e.g.
  `{"messages_sent": 20, "records_touched": 1000, "tickets_created": 5}`. Each consequential
  action type gets its own ceiling, so you can be generous with cheap reads and strict with
  irreversible writes *in the same agent*.
- **Unlimited unless you say otherwise.** Any action kind not in the dict is never capped. The
  harness only constrains what you explicitly choose to. The demo's `messages_sent: 3` is just a
  small number to keep the demo short — not a default.
- **No default cap ships in code, on purpose.** The right number is application-specific; a wrong
  default would be a false sense of safety. A high-volume notifier sets `messages_sent: 200`; a
  production-write agent sets `records_touched: 10` — same harness code, different config.
- **The value's home is per-agent config.** Limits live in each agent's
  `agents/<name>/limits.yaml` (token budget, spend cap, action limits, retry limits, timeouts),
  not in the harness package.

> Not built yet: the `limits.yaml` → `CostGovernor` loader. Today you construct the governor in
> Python (as the demo does); wiring it to YAML is a small, unblocked next step.

## Dependency rule

One-way: **agents import `qbiz_harness`; the harness imports nothing from `agents/` or `mcp/`.**
This keeps the package cleanly extractable later if an external consumer ever needs it.

## Develop

```bash
uv sync
uv run pytest
```
