# Agent Harness — Implementation Plan

**Scope:** Applies to all MCPs and Agents across the Qbiz agent ecosystem.
**Status:** Active. This is the working plan — supersedes the earlier draft in
`Slack_MCP/HARNESS_PLAN.md` (kept only as the original critique-of-slides reference).

---

## Relationship to the Executive Vision

Jeff's deck (`references/…Enterprise AI Agent Positioning…pptx`, slides 22–30) is the **Executive
Vision**. This document is the **Engineering Reality**. The reconciliation rule:

- Anything in the Vision that is missing from our code and is reasonable and doable → **we build it.**
- We add engineering detail the Vision doesn't touch (Jeff isn't a data engineer; he won't think
  of every technical detail, and that's expected) → **fine, as long as it doesn't contradict a
  *core* aspect of the Vision.**
- Small misalignments of judgment (e.g. cost governors at MEDIUM vs HIGH tier) are **ours to call**
  and not worth chasing.

This section is the standing instruction for how to treat future deck revisions, not a one-time merge.

---

## Decisions Locked

These are settled. Don't re-litigate them without a concrete new reason.

1. **The harness lives in `qbiz-agents`, not its own repo.**
   It is exactly the kind of reusable agent component this repo was created to hold, and its
   only consumer today is the agents in this repo. A separate repo would buy a second CI
   pipeline, a publish step, and cross-repo version pinning while serving a single in-repo
   client. Co-location also lets a harness change and the agent change it requires land in one
   atomic PR.

2. **It is a self-contained package at the top level: `harness/` (sibling to `mcp/`).**
   Own `pyproject.toml`, own `src/qbiz_harness/` package, own test suite. "Standalone package"
   is a *packaging* decision, not a *repo* decision — we get the clean boundary and independent
   tests without the cross-repo overhead.

3. **Dependency direction is one-way: agents import `qbiz_harness`; the harness imports nothing
   from agent or MCP code.** No back-references. This is what keeps a future extraction cheap
   (`git filter-repo` preserves history) if an external consumer ever appears.

4. **Access is open to any consultant for now.** No `CODEOWNERS` / restricted write access yet.
   That control is the *one* genuinely strong argument for tighter boundaries, but it only
   matters once this code lands on client hardware or an audit requirement narrows who may
   change the enforcement boundary. Revisit then — `OWNERS.yaml` already names `qbiz/platform`,
   which is enough until that day.

5. **External / cross-cutting concerns are deferred until they actually show up.** Multi-agent
   harness composition, separate-repo extraction, and compliance mapping are real but not yet
   load-bearing. They are recorded under *Deferred Concerns* below and addressed when a concrete
   use case forces them — not pre-built.

### Decide next (blocks Component 3)

**Agent identity injection mechanism.** Component 3 (tool access controls) cannot be built until
we decide how `agent_id` is established at process startup. Candidates: an environment variable
set by the launcher, or a signed token verified at harness init. Identity must **never** be read
from LLM output (it would be spoofable via prompt injection). This is the first open decision to
close before access-control code is written.

---

## What a Harness Is

A harness is the layer of code that enforces what an agent is *allowed* to do, regardless
of what it *reasons*. Instructions tell the agent what to do. The harness enforces it in code.

The distinction matters because:
- A sophisticated prompt injection can bypass instructions but cannot bypass code-enforced limits
- An edge case the developer didn't anticipate can cause instructions to fail silently
- Instructions degrade as models drift; code-enforced limits do not

> "Instructions are a request. The harness is enforcement."

### Probabilistic reasoning, deterministic consequences

LLM reasoning is inherently probabilistic — ask the same question twice and you may get different
answers, and that cannot be eliminated. The harness does not try to make the *reasoning*
deterministic. It makes the *consequences* deterministic: the action space is fixed and the blast
radius is bounded regardless of what the model reasons. That guarantee comes from enforcing, in
code:

- **Hard action limits** — maximum records touched, spend triggered, messages sent (Component 5)
- **Allowlists** — the agent can only reach explicitly permitted systems (Component 3)
- **Memory governance** — verified prior answers are retrieved, not re-derived with potential drift (Component 4)
- **HITL checkpoints** — a human clears irreversible actions before execution (Component 8)
- **Full audit trail** — every action logged, so forensic reconstruction is always possible (Audit Log)

The blast radius is deterministic even when the reasoning isn't.

---

## The Three Enforcement Layers

Each layer catches what the one before it misses.

| Layer | Mechanism | Characteristic |
|---|---|---|
| **1. Mechanical** | Rule-based code | Fast, cheap, cannot be reasoned around |
| **2. AI-powered** | Adversarial evaluator LLM | Reasoning-based, catches what rules can't anticipate |
| **3. Human judgment** | HITL checkpoints | Irreducible — what neither rules nor AI can fully evaluate |

All three layers should be present in any HIGH or VERY HIGH risk agent. LOW and MEDIUM risk
agents may omit the evaluator agent layer but should always have at minimum Layer 1 and Layer 3.

Layer 2 (the evaluator) is not only a semantic quality check on output. It also runs two
harness-aware checks that the mechanical layer can't: **harness gap detection** (does this agent
have all the controls appropriate to its scope, or is one missing?) and **behavioral drift flags**
(is the agent's output pattern diverging from its established baseline?). Both feed Component 7.

---

## What the Harness Protects Against — and What It Doesn't

Honest scoping. The harness is strong against some threats and only a backstop against others; say
so plainly rather than overselling. This framing is load-bearing for client conversations.

| Threat | Protection level | How / why |
|---|---|---|
| **Adversarial inputs** (prompt injection, jailbreaks, poisoned data sources) | **Strong** | Input wrapper + tool access controls enforce hard boundaries the model cannot reason around. |
| **Hallucination** | **Meaningful containment** | Output validator catches hallucinated tool calls and references to nonexistent data; evaluator catches semantically wrong output. The root cause lives in the model — the harness bounds the blast radius, it does not cure it. |
| **Bias & drift** | **Backstop, not primary fix** | Evaluator can be tuned to flag biased/drifting output and human review catches the rest, but the primary fix is model selection and instruction quality. The harness is the safety net, not the solution. |
| **Runaway behavior & cost** | **Strong** | Rate limits, spend caps, action limits, and kill switches stop an agent spiraling or racking up compute; orchestration controls prevent deadlock and infinite loops. |

The takeaway for positioning: higher risk does not mean "no" — it means the architecture has to
earn the trust. What the harness *cannot* fix (model-rooted bias, fundamental hallucination
tendency) is addressed upstream in model and instruction choice, not pretended away.

---

## The Eight Components

### Component 1 — Input Wrapper
**Type:** Custom Python — `src/qbiz_harness/input_wrapper.py`
**Size:** ~100–300 lines

Middleware that intercepts everything entering the LLM before the API call is made.
Cannot be bypassed by the model regardless of what it reasons.

Responsibilities:
- Prompt injection detection (regex + Guardrails AI / Rebuff)
- PII stripping from any user-supplied or external data before it reaches the model
- Rate limit check — reject if token budget or call rate is exceeded
- Safety instruction injection — appends mandatory scope/refusal rules to every prompt
- Input schema validation — reject malformed tool inputs before they reach tool handlers

```python
def wrap_input(prompt: str, context: dict) -> str:
    prompt = strip_pii(prompt)
    prompt = screen_injection(prompt)          # raises InputRejectedError if detected
    check_rate_limit(context["agent_id"])      # raises RateLimitError if exceeded
    prompt = inject_safety_instructions(prompt)
    return prompt
```

**Open detail:** Safety instructions should be stored as versioned config, not hardcoded in the
wrapper. Decide a versioning scheme when we write the first rubric.

---

### Component 2 — Output Validator
**Type:** Custom Python — `src/qbiz_harness/output_validator.py`
**Size:** ~100–300 lines

Intercepts the LLM's response before any downstream action is taken.

Responsibilities:
- Format validation — response matches expected schema
- Hallucinated tool call detection — tool name must be in the registered allowlist
- Out-of-scope content flagging — response references systems the agent is not permitted to use
- Factual consistency check — cited data exists in the sources the agent was given
- Downstream compatibility check — output will parse correctly by the next step in the pipeline

```python
def validate_output(response: str, context: dict) -> str:
    validate_format(response, context["expected_schema"])
    block_hallucinated_tool_calls(response, context["allowed_tools"])
    flag_out_of_scope(response, context["permitted_systems"])
    return response
```

**Partial-output policy:** If output is 90% valid but references one hallucinated tool —
reject-and-re-prompt for simple cases; strip-and-log for pipelines where a full retry is
expensive. Pick per call site.

---

### Component 3 — Tool-Level Access Controls
**Type:** Mixed (MCP schema + Python enforcement) — `src/qbiz_harness/access_controls.py`
**Size:** MCP schema + ~50 lines of permission enforcement

> **Blocked on the agent-identity decision above.** Build this only after the injection
> mechanism is settled.

Two-part system:
1. **Schema declaration** — MCP tool definitions declare what each tool accepts and returns.
   The schema is the spec; it does not enforce anything on its own.
2. **Runtime enforcement** — Python permission checks at the tool handler level verify the
   calling agent is allowed to invoke this tool with these arguments.

```python
ALLOWED_TOOLS: dict[str, set[str]] = {
    "incident-agent": {"send_message", "send_dm", "upload_file", "add_reaction"},
    "readonly-agent": {"get_channel_history", "list_channels", "find_user"},
}

def check_tool_permission(agent_id: str, tool_name: str) -> None:
    if tool_name not in ALLOWED_TOOLS.get(agent_id, set()):
        raise PermissionError(f"Agent {agent_id!r} is not permitted to call {tool_name!r}")
```

**Agent identity is injected, never trusted from the LLM.** `agent_id` comes from the startup
mechanism we settle above (env var or signed token), not from prompt context.

---

### Component 4 — Memory Scoping & Isolation
**Type:** Custom Python — `src/qbiz_harness/memory.py`
**Size:** ~50 lines (isolation) + policy decisions below

> Only build this if agents share a memory backend. If memory is per-agent, skip.

Every read and write to shared memory (vector DB, key-value store, episodic cache) is
prefixed with an agent-specific namespace. Agents cannot read each other's memory regardless
of what they reason.

```python
class ScopedMemory:
    def __init__(self, agent_id: str, backend: VectorDB):
        self._prefix = f"{agent_id}::"
        self._backend = backend

    def write(self, key: str, value: str) -> None:
        self._backend.upsert(f"{self._prefix}{key}", value)

    def read(self, key: str) -> str | None:
        return self._backend.get(f"{self._prefix}{key}")
```

Namespace isolation is the easy 50 lines. The decisions that actually matter, to settle when a
shared backend appears:
- **Cross-session persistence** — what survives a restart? All / some / none?
- **Memory TTL** — stale resolutions are worse than no memory if the failure mode changed
- **What gets written** — deciding *what* to memorize is at least as important as isolation
- **Poisoning via legitimate input** — clean-looking data can write bad patterns over time;
  isolation does not prevent this

---

### Component 5 — Cost & Compute Governors
**Type:** Custom Python — `src/qbiz_harness/cost_governor.py`
**Size:** ~75 lines

Hard limits enforced in code, across two dimensions:

- **Cost limits** — token budget and USD spend. Fire *before* an API call (token estimation)
  where possible, *after* otherwise (spend tracking).
- **Action limits** — counts of consequential operations: records touched, messages sent, tool
  calls made. The Vision lists these explicitly ("maximum records touched, spend triggered,
  messages sent — in code"), and they are how the *blast radius* — not just the bill — is bounded.
  A spend cap stops runaway cost; an action cap stops a cheap-but-destructive loop (e.g. an agent
  that sends 500 Slack messages well under the token budget).

The governor also carries a **kill switch** (a hard global stop, independent of any single limit)
and supports **redundancy detection** — refusing work it has already done this run.

```python
class CostGovernor:
    def __init__(
        self,
        token_limit: int,
        spend_limit_usd: float,
        action_limits: dict[str, int] | None = None,  # e.g. {"messages_sent": 20, "records_touched": 1000}
    ):
        self.tokens_used = 0
        self.spend_usd = 0.0
        self.token_limit = token_limit
        self.spend_limit = spend_limit_usd
        self.action_limits = action_limits or {}
        self.action_counts: dict[str, int] = {}
        self._killed = False

    def pre_call(self, estimated_tokens: int) -> None:
        if self._killed:
            raise BudgetExceededError("Kill switch engaged")
        if self.tokens_used + estimated_tokens > self.token_limit:
            raise BudgetExceededError("Token limit reached")

    def post_call(self, tokens_used: int, cost_usd: float) -> None:
        self.tokens_used += tokens_used
        self.spend_usd += cost_usd
        if self.spend_usd > self.spend_limit:
            raise BudgetExceededError(f"Spend limit ${self.spend_limit} exceeded")

    def record_action(self, kind: str, count: int = 1) -> None:
        """Call before a consequential action (send, write, touch). Fires before the action runs."""
        if self._killed:
            raise BudgetExceededError("Kill switch engaged")
        projected = self.action_counts.get(kind, 0) + count
        limit = self.action_limits.get(kind)
        if limit is not None and projected > limit:
            raise BudgetExceededError(f"Action limit for {kind!r} reached ({limit})")
        self.action_counts[kind] = projected

    def kill(self) -> None:
        self._killed = True
```

The cost optimization waterfall (apply before any LLM call):

1. **Can a deterministic rule, SQL, or script answer this?** → Use it. Zero LLM cost.
2. **Is the result already cached from a prior run?** → Retrieve it. Near-zero cost.
3. **Does this require LLM reasoning?** → Route to smallest capable model (Haiku/Flash/mini tier).
4. **Does this require complex judgment or adversarial evaluation?** → Escalate to frontier model.
5. **Hitting spend threshold?** → Pause, fire HITL checkpoint, wait for human to continue or cancel.

**Still to specify:** cache invalidation strategy (when is a cached result still valid?),
what "smallest capable model" means per task type (needs empirical benchmarking), pre-call token
estimation (tiktoken or similar), and the cost of the harness itself (the evaluator adds a full
API call per run).

---

### Component 6 — Orchestration Controls
**Type:** Custom Python — `src/qbiz_harness/orchestration.py`
**Size:** ~100 lines

Prevents runaway behavior: infinite loops, deadlock, unbounded retry chains. Also owns
**fallback paths** — when a step exhausts its retries, the agent routes to a defined fallback
(degraded-mode answer, alternate tool, or escalate-to-human) rather than failing hard or spinning.

```python
import asyncio
import functools

def with_retry(max_attempts: int = 3, backoff_base: float = 2.0):
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return await asyncio.wait_for(fn(*args, **kwargs), timeout=30.0)
                except asyncio.TimeoutError:
                    if attempt == max_attempts - 1:
                        raise
                    await asyncio.sleep(backoff_base ** attempt)
        return wrapper
    return decorator

class LoopGuard:
    def __init__(self, max_iterations: int = 10):
        self._count = 0
        self._max = max_iterations

    def tick(self) -> None:
        self._count += 1
        if self._count > self._max:
            raise LoopLimitError(f"Agent exceeded {self._max} iterations — escalating to human")
```

**Still to specify:** partial-success recovery (if step 3 of 5 fails — start over or resume?),
deadlock handling in multi-agent pipelines, and **per-tool** timeouts (a global 30s is wrong for
most tools — timeouts belong on the tool, not the wrapper).

---

### Component 7 — Evaluator Agent
**Type:** Markup / Prompt (one additional API call) — rubric lives per-agent (see config below)
**Size:** 1 API call + evaluator rubric prompt

> Build last. Rubric quality depends on seeing real agent outputs to know what to evaluate against.

A second, independent LLM configured to be skeptical. It reviews the primary agent's output
before any action is taken. Must be a *different* model than the one that generated the output —
same-model self-evaluation reliably gives inflated scores.

**Evaluator rubric should cover:**
- Is the claimed root cause consistent with the evidence actually retrieved?
- Are any tool calls referenced in the output real and in scope for this agent?
- Does the recommended action fall within the agent's permitted scope?
- Is there a simpler explanation the agent may have overlooked?
- Are there harness controls that should exist given the agent's scope but appear absent? (**harness gap detection**)
- Does this output diverge from the agent's established behavioral baseline? (**behavioral drift flag**)

**The evaluator has its own blast radius.** It can hallucinate too. If evaluator confidence is
below a threshold, escalate to a HITL checkpoint rather than treating its output as ground truth.

**Still to specify:** which scenarios to run it against (real edge cases from the actual business
process, not synthetic happy paths), evaluator model selection (which *other* model, and the
tradeoffs), and the feedback loop (findings should feed back into instruction refinement — no
mechanism described yet).

---

### Component 8 — Human Checkpoints (HITL)
**Type:** Mixed (Python notification + integration) — `src/qbiz_harness/hitl.py`
**Size:** ~100 lines + notification integration

Mandatory pauses before consequential actions. The agent posts a notification, waits for an
explicit approval signal, then proceeds or halts. The Slack MCP (`mcp/mcp_slack/`) already
provides `send_message` and `request_approval` — HITL wraps those.

For the Qbiz demo and Slack-based deployments:
1. Agent posts decision prompt to Slack with ✅/❌ instructions
2. Harness blocks on `wait_for_reaction(channel, ts, timeout=120)`
3. On ✅: agent continues; on ❌: agent halts and logs the rejection; on timeout: per policy below

```python
async def hitl_checkpoint(
    slack_mcp,
    channel: str,
    prompt: str,
    timeout: int = 120,
) -> bool:
    ts = await slack_mcp.send_message(channel=channel, text=prompt)
    result = await slack_mcp.request_approval(
        channel=channel,
        thread_ts=ts,
        timeout_seconds=timeout,
    )
    log_audit(action="hitl_checkpoint", decision=result["decision"], user=result.get("user"))
    return result["decision"] == "approved"
```

**Timeout policy is per-agent and must be documented.** Pick one:
- **Fail closed** — no response = no action (safest; default for HIGH+)
- **Fail open** — no response = proceed after timeout (only for LOW risk, time-sensitive)
- **Escalate** — no response = page a secondary contact and pause indefinitely

**Still to specify:** unattended/overnight behavior, how to give the approver enough context in
the message, and the audit trail (who approved, exact state at approval, whether the subsequent
action matched the prompt).

---

### Component (cross-cutting) — Audit Log
**Type:** Custom Python — `src/qbiz_harness/audit.py`

Not one of the Vision's eight, but referenced throughout it (it appears in the risk table as
"audit trail / audit logging" rather than as a numbered component). We treat it as **cross-cutting
infrastructure every other component logs through**, not a ninth component — an engineering
refinement that doesn't change the Vision's count. The audit log is a **first-class data product,
not a log file.** For any HIGH+ agent:
- Append-only storage (CloudWatch, BigQuery, S3 with object lock)
- Structured events with a consistent schema: `{agent_id, action, inputs, outputs, ts, user, decision}`
- Queryable for forensic reconstruction — "what did the agent do between 14:00 and 14:30?"
- HITL decision (who approved, what they saw, when) stored alongside the action

---

## Components Are Opt-In at the Call Site

The harness does **not** wrap every LLM call identically.
- **Always-on:** Components 1 (input wrapper), 2 (output validator), 5 (cost governor).
- **Risk-gated:** Components 3 (access control), 7 (evaluator), 8 (HITL) fire based on the risk
  profile of the *specific action* — listing channels is low-stakes; approving a production
  rollback needs all of them.

---

## Risk Tiering

Right-size the harness to the use case. Not every agent needs all eight components.

| Risk Level | Example | Minimum Components | QA Gates |
|---|---|---|---|
| LOW | Internal read-only analysis agent | Logging + light output validation | — |
| MEDIUM | Read/analyze enterprise operator | Components 2, 5, 8 + audit trail | Gate 1 |
| HIGH | Write-capable or customer-facing agent | Components 1–6 + evaluator + audit logging | Gates 1–2 |
| VERY HIGH | Regulated industry — financial, healthcare, irreversible actions | All eight + compliance documentation + red team | Gates 1–2–3 |

**The Agentic Incident DAG (Airflow Summit demo) is HIGH** — it writes to Slack and creates
Jira tickets. Minimum: Components 1, 2, 3, 5, 6, 8 + audit trail.

### Worked examples

The Vision walks two canonical agents through all eight components — use them as the reference
shape when scoping a new agent:

- **Data Quality Monitoring Agent (slide 28)** — monitors pipelines 24/7, reads warehouse + catalog,
  cannot write to production, escalates root-cause analysis to a human after 3 unresolved iterations.
  HIGH tier. This is the Vision's everyday example.
- **Credit Risk Monitoring Agent — financial services (slide 29)** — VERY HIGH / highest risk tier,
  full three-gate harness, zero write access, customer PII never persisted, single-account scope
  with bulk-processing tripwires, compliance-tuned evaluator. This is the Vision's regulated example.

Our **Agentic Incident DAG** is the concrete agent we are actually building, and it sits at HIGH
alongside the data-quality example — same tier, same minimum components. It is not in Jeff's deck;
that's fine (it's our build target, not a positioning example) and it doesn't contradict the
Vision. Keep it as our reference implementation; reach for Jeff's two examples when talking shape
with the team or a client.

---

## Quality Gates

### Gate 1 — Automated Checks (runs on every build, blocks deployment on failure)

- Unit tests for every tool (input/output contract)
- Linting and type checking of all harness code
- Access control verification — explicitly test that the agent *cannot* call tools outside its allowlist
- Hard limit enforcement — test that cost/token governors fire at the configured threshold
- Audit logging validation — confirm every action type produces a log entry
- Tool schema consistency — MCP schema matches actual Python function signatures

### Gate 2 — Evaluator Agent

- Run against a suite of real-world scenarios from the actual business process (not synthetic cases)
- Explicitly test edge cases: tool returns null, required field missing, upstream data empty
- Evaluator checks harness completeness — does the agent have all controls appropriate to its scope?
- Evaluator findings documented and fed back into instruction and harness refinement before Gate 3

### Gate 3 — Human Red Team (required for HIGH and VERY HIGH)

- Craft prompt injection attempts via the channels the agent reads (email, Slack, documents)
- Attempt to get the agent to take out-of-scope actions
- Test edge cases the automated evaluator didn't generate
- For regulated industry: compliance review mapping harness controls to regulatory requirements
- Gate 3 findings always loop back to the build phase — no "accept and ship anyway" path

---

## Repository Layout

```
qbiz-agents/
├── harness/                        # this package — sibling to mcp/
│   ├── HARNESS_PLAN.md             # this document
│   ├── OWNERS.yaml
│   ├── pyproject.toml              # package: qbiz-agent-harness, src/qbiz_harness
│   ├── src/qbiz_harness/
│   │   ├── input_wrapper.py        # Component 1
│   │   ├── output_validator.py     # Component 2
│   │   ├── access_controls.py      # Component 3 (blocked on identity decision)
│   │   ├── memory.py               # Component 4 (only if shared backend)
│   │   ├── cost_governor.py        # Component 5
│   │   ├── orchestration.py        # Component 6
│   │   ├── hitl.py                 # Component 8
│   │   └── audit.py                # cross-cutting audit log
│   └── tests/                      # Gate 1 lives here
├── agents/<agent_name>/            # per-agent config (no harness code changes)
│   ├── permissions.yaml            # which tools this agent can call
│   ├── limits.yaml                 # token budget, spend cap, retry limits, timeouts
│   ├── evaluator_rubric.md         # Component 7 adversarial prompt
│   └── AGENTS.md                   # agent identity, scope, operating rules (versioned)
└── mcp/                            # existing MCP servers (Slack, Astro/Airflow, …)
```

Reminder: **agents import `qbiz_harness`; the harness imports nothing from `agents/` or `mcp/`.**

---

## Implementation Order

1. [ ] Scaffold `harness/` package — `pyproject.toml`, `src/qbiz_harness/`, `tests/`
2. [ ] Build Components 5, 6, 8 first — cost governors, orchestration controls, HITL
       (most universally needed, least agent-specific; HITL reuses the Slack MCP)
3. [ ] Add the cross-cutting audit log (`audit.py`) alongside — everything else logs through it
4. [ ] Add Components 1, 2 — input wrapper and output validator
       (require PII type definitions and tool allowlists per agent)
5. [ ] **Close the agent-identity decision**, then add Component 3 — tool access controls
6. [ ] Add Component 4 — memory scoping (only if agents share a memory backend)
7. [ ] Add Component 7 — evaluator agent (last; rubric quality needs real agent outputs)
8. [ ] Implement Gate 1 automated tests for each component as it is built
9. [ ] Run Gate 2 (evaluator) against the Agentic Incident DAG scenarios before demo
10. [ ] Gate 3 (red team) is post-demo unless the demo is used in a client-facing context

---

## Sizing — What Drives the 500–1500 Line Range

The 3× range is meaningless without knowing what moves it. The deciding factors:
- Number of distinct tools the agent can call (access control table grows linearly)
- Whether the evaluator requires a custom rubric or a generic one
- Whether HITL is synchronous (blocks execution) or asynchronous (fires and continues)
- Number of distinct PII types requiring custom stripping logic
- Whether the memory backend is shared (requires scoping) or per-agent (does not)

---

## Deferred Concerns

Real, but not load-bearing yet. Addressed when a concrete use case forces them — not pre-built.

1. **Multi-agent harness composition** — when agent A calls agent B, what is the trust model?
   Does B's harness fire independently? If A is compromised, can it pass malicious inputs that
   bypass B's input wrapper? Decide when we first chain agents.
2. **Separate-repo extraction** — only when a non-agent consumer needs the harness without the
   whole repo, or audit access must be narrower than repo write access. Cheap to do later given
   the one-way dependency rule.
3. **Harness versioning & migration** — running old and new harnesses in parallel for comparison
   across a model-generation change. Revisit at the first such migration.
4. **Observability spec** — *what* to monitor, alert thresholds, what "behavioral drift" looks
   like. LangSmith / Arize are candidate COTS tools; spec the signals when we instrument.
5. **Harness security / supply chain** — the harness is itself the enforcement boundary. Who
   audits it, how often, and dependency-pinning for Guardrails AI et al. Pairs with the
   `CODEOWNERS` decision — both trigger when code reaches client hardware.
6. **`CODEOWNERS` / restricted write** — see Decision 4. Valid approach once this lands on client
   hardware; open to all consultants until then.
