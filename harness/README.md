# qbiz-agent-harness

Code-enforced limits on what Qbiz agents are *allowed* to do, regardless of what they reason.
Instructions are a request; the harness is enforcement.

See [HARNESS_PLAN.md](HARNESS_PLAN.md) for the full design — the eight components, risk tiers,
and quality gates.

## Status

Scaffold only. The decision-independent foundation is in place:

- `src/qbiz_harness/exceptions.py` — the `HarnessError` hierarchy every component raises through.

Component modules land per the build order in the plan, starting with cost governors,
orchestration controls, and HITL. A few design decisions (agent-identity injection, shared vs.
per-agent memory) are pending team review before the components they gate are built.

## Dependency rule

One-way: **agents import `qbiz_harness`; the harness imports nothing from `agents/` or `mcp/`.**
This keeps the package cleanly extractable later if an external consumer ever needs it.

## Develop

```bash
uv sync
uv run pytest
```
