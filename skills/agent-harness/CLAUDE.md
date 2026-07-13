# Claude-specific notes for agent-harness

- Invoke via the Skill tool for the full pattern. `qbiz_harness` is a plain Python import, not an
  MCP server — there's nothing to "connect"; if the package isn't a dependency yet, add it (see
  [SETUP.md](SETUP.md)) rather than looking for it in your tool list.
- `hitl_checkpoint` is async and blocks. Await it and branch on the result — don't poll an
  approval channel in a loop to simulate it (the same rule as
  [slack-bot-setup](../slack-bot-setup/CLAUDE.md)).
- Parallelize independent read-only setup (e.g. loading two agents' separate `AuditLog`/
  `CostGovernor` instances) where it's genuinely independent; keep the guard-then-act sequence
  inside one agent step sequential — `loop.tick()` → `validate_output` → `governor.record_action`
  → the actual tool call → `audit.record` is a strict order, not a parallelizable batch.

## How much judgment you're trusted with scales with model strength

This skill spans a real judgment gradient: deciding *what* limits an agent needs (a design
decision) vs. *wiring* the controls at the call site (mechanical). Calibrate which side of that
line you're on by which model is doing the work.

### Opus (architect tier)

You're trusted to make the policy calls, not just wire the controls:

- Classify the agent's risk tier (LOW–VERY HIGH — see `harness/HARNESS_PLAN.md`) before choosing
  which controls apply and whether HITL is required.
- Propose concrete `action_limits`, `token_limit`, `spend_limit_usd`, and `TimeoutPolicy` values
  for a new agent, and be ready to justify them in a PR description — a `limits.yaml` doesn't
  exist yet, so these values live in your code and should read like a deliberate decision, not a
  placeholder.
- Decide the fallback behavior on each `HarnessError` (re-prompt vs. escalate vs. halt) based on
  what the specific action means for the agent's job — this is exactly the kind of call the skill
  leaves to you rather than baking into the harness.

### Sonnet (implementer tier)

Follow the documented pattern; don't redesign it:

- Use the minimal pattern in [SKILL.md](SKILL.md) close to verbatim: construct controls once,
  guard every consequential step in the documented order, log both allowed actions and
  interventions.
- If limit values aren't given to you (by the task, a prior decision, or existing agent code),
  ask rather than inventing them — or use the SKILL.md example values explicitly labeled as
  placeholders for a human to confirm.
- Don't build a config loader, a generic "harness wrapper" abstraction, or anything from the
  "What's not ready yet" list — those are out of scope until the plan says otherwise.

### Haiku / small-model / subagent tier

Treat this as a fixed checklist, not a design space:

- Only import and call the specific controls the parent task names, at the exact point it names.
  Do not decide on your own initiative that an action also needs, say, a `LoopGuard` it wasn't
  asked to have.
- Never choose a numeric limit, timeout policy, or risk tier yourself. If one isn't handed to you
  explicitly, stop and ask — don't guess a "reasonable" number.
- **Never catch a `HarnessError` and route around it.** The most common failure at this tier is
  "fixing" a `BudgetExceededError` / `OutputRejectedError` / `HitlEscalationRequired` by retrying
  the same action, loosening the limit inline, or swallowing the exception so the agent proceeds
  anyway. If a `HarnessError` fires, record it via `audit.record_intervention(...)` and stop —
  that is the entire job, not a bug to work around.
- Don't add retry loops, helper wrappers, or extra abstraction around the harness calls — call the
  imported functions directly, in the order shown.
