---
model: gemini
---

# Gemini-specific notes for agent-harness

- `qbiz_harness` is a plain Python import, not an MCP server — there is nothing to connect. Add it
  as a dependency (see [SETUP.md](SETUP.md)) if it isn't already one.
- `hitl_checkpoint` is async and blocking — await it and branch on the result; don't poll for an
  approval to simulate it.
- Keep the per-step order strict and sequential: loop guard tick → output validation → action-cap
  check → the actual tool call → audit record. This is not a batch of independent calls.

## Judgment scales with model tier

- **Pro (or the strongest available tier):** you may propose the agent's risk tier, its
  `action_limits`/`token_limit`/`spend_limit_usd`, and the fallback behavior (re-prompt / escalate
  / halt) for each `HarnessError` — these are deliberate design decisions this skill leaves to you.
- **Flash (or a smaller/faster tier):** treat the skill as a checklist. Only wire the specific
  controls you're told to, using limit values you were given — never invent a numeric cap or
  timeout policy yourself. Most importantly: **never catch a harness exception and work around
  it** (retrying the same action, loosening a limit, or swallowing the error to let the agent
  proceed). Record the intervention and stop; that is the correct outcome, not a failure to fix.
