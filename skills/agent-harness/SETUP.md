# Setup: agent-harness

There's no server to stand up — `qbiz_harness` is a plain Python package
(`harness/` in this repo, distributed as `qbiz-agent-harness`). Setup is just adding it as a
dependency of the agent you're building.

## Add the dependency

From your agent's package (managed with `uv`, as the rest of this repo is), point at the local
`harness/` path:

```toml
[project]
dependencies = [
    "qbiz-agent-harness",
]

[tool.uv.sources]
qbiz-agent-harness = { path = "../harness", editable = true }
```

Adjust the relative path to wherever your agent's `pyproject.toml` sits relative to `harness/`.
Then:

```bash
uv sync
```

## Verify

```python
from qbiz_harness import CostGovernor, AuditLog
```

should import cleanly. If you're wiring a HITL gate, you'll also need an `ApprovalTransport` — the
[slack-bot-setup](../slack-bot-setup/SKILL.md) skill's `request_approval` is the reference
implementation; see its [SETUP.md](../slack-bot-setup/SETUP.md) to stand that up first.

## Further reference

- `harness/README.md` — full consultant guide, the source this skill is drawn from
- `harness/HARNESS_PLAN.md` — the eight-component design, risk tiers, fleet operation
- `harness/demo/incident_runaway.py` — a no-LLM walkthrough of the harness stopping a runaway
  agent (cost cap, loop guard, HITL rejection, kill switch, all through the audit trail):
  `uv run python demo/incident_runaway.py` from `harness/`
