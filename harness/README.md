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
- `src/qbiz_harness/audit.py` — cross-cutting **append-only audit log** (local JSONL for now;
  production storage backend is decision `[D4]`).
- `src/qbiz_harness/hitl.py` — **Component 8**: human approval checkpoints. Wraps an injected
  approval transport (the Slack MCP's `request_approval`); per-agent timeout policy `[D6]`
  (fail-closed / fail-open / escalate), defaulting to fail-closed for HIGH+.

Still to come, per the plan's build order: input wrapper + output validator (Phase 2), then the
decision-gated pieces — access controls (`[D1]`), memory scoping (`[D2]`), evaluator (`[D3]`).

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
