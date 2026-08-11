# Agent Harness — Implementation Plan

**Scope:** Applies to all MCPs and Agents across the Qbiz agent ecosystem.
**Status:** Active. This is the working plan — supersedes the earlier draft in
`Slack_MCP/HARNESS_PLAN.md` (kept only as the original critique-of-slides reference).

---

## Relationship to the Executive Vision

Jeff's deck (slides 22–30) is the **Executive Vision**. This document is the **Engineering
Reality**. The reconciliation rule:

- Anything in the Vision that is missing from our code and is reasonable and doable → **we build it.**
- We add engineering detail the Vision doesn't touch (Jeff isn't a data engineer; he won't think
  of every technical detail, and that's expected) → **fine, as long as it doesn't contradict a
  *core* aspect of the Vision.**
- Small misalignments of judgment (e.g. cost governors at MEDIUM vs HIGH tier) are **ours to call**
  and not worth chasing.

This section is the standing instruction for how to treat future deck revisions, not a one-time merge.

**Source of truth for the deck:**
<https://docs.google.com/presentation/d/178LWTphdfSCooNB4nF5uSJOovXlnwTmy> — the live deck in the
Qbiz Google Drive (Qbiz-only; not accessible to non-Qbiz folks). A local copy lives at
`references/` (gitignored) purely so tooling without Drive access can read it; the Google Slides
link is canonical, so check it for the current version before treating the local copy as current.

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

### Decide next

The full list of open decisions, what each blocks, and when it's needed lives in
**[Required Decisions](#required-decisions)** below the Implementation Order. The two team
decisions on the critical path to *client* engagement (the hard gate — the Airflow demo is only a
soft target) are **D1 (agent-identity injection)** and **D3 (LLM provider + evaluator model)** —
start there.

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
| **Runaway behavior & cost** | **Strong** | Rate limits, spend caps, action limits, and kill switches stop an agent spiraling or racking up compute; orchestration controls prevent deadlock and infinite loops; the model-tier policy caps per-activity model strength so a trivial step cannot self-escalate to a frontier model. |

The takeaway for positioning: higher risk does not mean "no" — it means the architecture has to
earn the trust. What the harness *cannot* fix (model-rooted bias, fundamental hallucination
tendency) is addressed upstream in model and instruction choice, not pretended away.

---

## The Enforcement Perimeter — Ring 1 (Harness) vs. Rings 2–3 (Client Infrastructure)

**This section exists to answer a question that comes up in nearly every client conversation:**
*"Can this stop our salespeople from using a frontier model to build presentations?"* (or the
general form: "can it govern which models which people use, company-wide?"). The honest answer is a
scoping answer, and getting it right keeps us from overselling the harness *and* from letting the
harness scope-creep into problems it structurally cannot solve. **Point the client at the right
layer instead.**

**The governing principle** (the same one the whole harness rests on): enforcement only holds at a
**chokepoint the caller cannot route around.** The harness owns the innermost chokepoint — it is
*inside the agent's code path*, so an agent physically cannot make a model call without passing
through it (this is what the **Model-Tier Policy**, Component 5's extension, does for model strength).
The further out from our code you push the chokepoint, the leakier it gets — and a company-wide
"which people may use which models" policy lives in the two outer rings, which are **client
infrastructure, not harness code.**

| Ring | What flows through it | Enforcement point | Owner | Control strength |
|---|---|---|---|---|
| **1 — Agent code** | LLM calls our agents make | **The harness** (`ModelPolicy`, cost governor, access controls, …) | **Us** — this plan | **Total** — in-process, un-bypassable |
| **2 — Programmatic API use** | Any code/employee hitting an LLM *API* | An **LLM gateway/proxy** + blocked direct egress | **Client platform/security team** | **Strong** — *if* the bypass is closed |
| **3 — Third-party AI SaaS** | People using ChatGPT / Claude / Copilot / Gemini in a browser | Vendor admin controls + CASB/network + tenant restrictions | **Client IT/security + procurement** | **Partial** — never airtight |

The harness delivers Ring 1 in full. Rings 2 and 3 are what we *advise the client to build* — and
deliberately **not** things we fold into `qbiz_harness` (they have no place inside an in-process
agent library; see the one-way-dependency discipline and *Deferred Concerns*). What follows is the
guidance to give.

### Ring 2 — the corporate generalization of the harness (client builds this)

For all *programmatic* model access across the company, the client applies the harness's own
"enforce, not route" pattern one layer out: route every model call through a single egress
**gateway** that authenticates the caller against the corporate IdP, looks up `group → allowed
tier`, and **rejects or downgrades** disallowed requests. It is the `ModelPolicy` check, moved from
in-process to network egress.

- **Gateway options to point them at:** LiteLLM, Portkey, Cloudflare AI Gateway, Kong AI Gateway, or
  homegrown. All do identity-aware model allow/deny + budgets + logging.
- **The linchpin — close the bypass.** The gateway is only a control if it is the *only* path:
  the client must **block direct egress** to `api.openai.com` / `api.anthropic.com` / etc. at the
  firewall, exactly as the harness's model policy is only real because the LLM can't supply its own
  policy. A gateway with an open bypass is a suggestion, not a control. **This is the single point
  clients most often miss — lead with it.**
- **Identity is the spine.** "Salespeople" is a group in Okta / Entra / Google Workspace; every ring
  keys its policy off that group. If the client wants the policy authored once and enforced
  everywhere, that is a policy engine (OPA / Cedar) the gateway queries.
- **Bonus they already understand from Ring 1:** the gateway's allow/deny/downgrade logs are the
  company-wide version of our **harness-intervention-rate** metric (see *Fleet Operation*) — same
  "was that a real catch or a too-tight limit?" telemetry, scaled to the whole org.

### Ring 3 — where the salesperson-and-presentation example actually lives (hardest)

The catch that makes the classic question hard: a salesperson in ChatGPT or Gamma **isn't touching
any API the client owns**, so a gateway is useless here. Enforcement splits by whether the tool is
sanctioned:

- **Sanctioned tool → vendor admin console.** ChatGPT Enterprise, Claude Enterprise, and M365
  Copilot expose SSO/SCIM and — increasingly, but *not* universally — **per-group model gating**. So
  "sales gets the mid tier, not the frontier reasoning model" can be a workspace admin setting *if
  the vendor sells that control.* This is really a **procurement lever**: buy the SKU that exposes
  the gating you need, and negotiate for it when it doesn't.
- **Unsanctioned / shadow AI → the network.** Personal ChatGPT accounts and free Claude can't be
  configured (you don't control the product), so control falls to a **CASB** (Netskope, Zscaler,
  Palo Alto Prisma) that recognizes AI-SaaS traffic and blocks/coaches by user identity, plus
  **tenant restrictions** (Entra tenant restrictions / Google context-aware access) that allow the
  *corporate tenant* of a tool while blocking personal logins.

### Before recommending any of it — interrogate the "why"

The right lever depends on the client's actual goal, and "cap the tier" is frequently **not** it.
Diagnose first:

| Client's real concern | Correct primary lever | Note |
|---|---|---|
| **Cost** (frontier is expensive) | Gateway **downgrade + per-group budgets** (Ring 2) | Prefer downgrade over hard block — denial breeds workarounds |
| **Data governance** (sensitive data leaving to certain vendors) | **DLP + approved-vendor allowlist** | Model *tier* is nearly a red herring here; the concern is the endpoint and the data |
| **Quality / brand** (presentations must use approved templates) | A **tooling mandate**, not a model control | Not a harness/gateway problem at all |
| **Capability gating** (this role shouldn't have frontier reasoning) | Ring 2/3 tier caps | The rarest; worth challenging whether it's the real requirement |

### The part clients underestimate — and our standing recommendation

Ring 3 is **never watertight**, and a pure "no" **manufactures shadow AI** (block the frontier tool
with no alternative and people use their phones). The pattern that actually holds company-wide is
enforcement **paired with a sanctioned, good-enough path**: give the group an approved mid-tier tool
that does the job, gate the frontier one, and **audit the residual**. That is the same posture the
harness takes at Ring 1 — bound the blast radius, log every intervention, and treat a recurring
block as a signal the limit may be mis-set, not an automatic win.

**Consulting note:** this whole section is a QBiz advisory surface, not a harness feature —
"model-tier entitlements and AI-usage governance, company-wide" is a natural companion to the
readiness-assessment work. When a client asks the salesperson question, the deliverable is this
ring model and the tool pointers above, **not** a promise to extend the harness.

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

   Steps 3–4 are the *routing* decision; the **Model-Tier Policy** (below) is what makes it
   *enforceable* — the router picks the model, the policy caps what it is allowed to pick per activity.
5. **Hitting spend threshold?** → Pause, fire HITL checkpoint, wait for human to continue or cancel.

**Still to specify:** cache invalidation strategy (when is a cached result still valid?),
what "smallest capable model" means per task type (needs empirical benchmarking — now owned by the
**Model-Tier Policy** below), pre-call token estimation (tiktoken or similar), and the cost of the
harness itself (the evaluator adds a full API call per run).

---

### Component (extension of 5) — Model-Tier Policy
**Type:** Custom Python — `src/qbiz_harness/model_policy.py`
**Size:** ~75 lines + per-cohort model config

Like the audit log, this is **not one of the Vision's eight** — it is an engineering refinement to
the *cost & compute governance* dimension (Component 5), which is why it lives next to
`cost_governor.py`. Model choice is the single biggest cost-and-capability lever an agent has, so
the harness governs it the way it governs spend and action counts: **enforce a bound in code, don't
let the model reason its way past it.** ("Instructions are a request; the harness is enforcement" —
a step *told* to use a weak model can decide otherwise; a tier *cap* cannot be reasoned around.)

**Enforce, not route.** The launcher/orchestrator still *picks* which model runs a step — routing is
reasoning-adjacent and stays out of the harness. The harness *caps* that choice: each activity
declares an allowed tier band, and a call requesting a model outside the band is rejected **before**
the API call, exactly as `CostGovernor.pre_call` rejects an over-budget call. A weak-tier "file a
Jira ticket" step cannot escalate itself to a frontier model; an investigation step cannot be
silently downgraded below its floor.

Motivating case (the Airflow demo): incident *investigation* runs at MID (Sonnet / Gemini Pro) with
reasoning latitude; the mechanical steps — open Jira ticket, post Slack message, status update — are
capped at WEAK (Haiku / Flash). Same DAG, one tier band per activity. This also *closes the loop*
with the `agent-harness` skill, whose `CLAUDE.md`/`GEMINI.md` already tell the model which tier to
use per task type: the skill advises the tier, this component enforces it.

**Tiers are provider-agnostic ordinals.** `WEAK < MID < FRONTIER`. Concrete models map to a tier via
config (`[D8]`), never hardcoded — forced by the open provider question `[D3]` (Qbiz may run Gemini,
not Claude): `weak: [claude-haiku-*, gemini-flash-*]`, `mid: [claude-sonnet-*, gemini-pro-*]`,
`frontier: [claude-opus-*]`. The guard resolves a concrete model string to its tier, then compares
ordinals — so the same band works across providers.

Two bounds, deliberately different strengths:
- **Ceiling (`max_tier`) — hard, always enforced.** Cost / blast-radius. The ironclad, demoable
  guarantee: *a trivial step can never burn a frontier model.*
- **Floor (`min_tier`) — template default, opt-in-hard.** Quality. "Don't investigate an incident
  with a weak model." But "too weak" is a *judgment*, not a safety boundary — the real quality
  backstop is the evaluator (Component 7). So the floor ships as a cohort/template default that a
  specific activity can promote to a hard reject when the quality risk warrants it.

```python
class Tier(IntEnum):
    WEAK = 1
    MID = 2
    FRONTIER = 3

class ModelPolicy:
    """Caps the model tier per activity. Policy comes only from construction-time config — never
    from LLM output — so no reasoning can widen it. Mirrors CostGovernor.pre_call: the check fires
    before the API call, so the wrong-tier call never happens."""

    def __init__(self, tier_map: dict[str, Tier], activities: dict[str, ActivityBand]):
        self._tier_of = tier_map          # concrete model name -> Tier
        self._bands = activities          # activity -> (min_tier, max_tier, floor_hard)

    def check(self, activity: str, model: str) -> None:
        tier = self._tier_of.get(model)
        if tier is None:                                   # fail closed: ungoverned model
            raise ModelPolicyError(f"Model {model!r} is not tier-mapped; refusing (ungoverned)")
        band = self._bands.get(activity)
        if band is None:                                   # fail closed: ungoverned activity
            raise ModelPolicyError(f"No model band for activity {activity!r}; refusing")
        if tier > band.max_tier:
            raise ModelPolicyError(
                f"{activity!r} permits at most {band.max_tier.name}; {model!r} is {tier.name}"
            )
        if band.floor_hard and tier < band.min_tier:
            raise ModelPolicyError(
                f"{activity!r} requires at least {band.min_tier.name}; {model!r} is {tier.name}"
            )
```

`ModelPolicyError` is a new leaf on the `HarnessError` hierarchy (`exceptions.py`), so the call-site
exception boundary stamps a `harness_intervention` audit event automatically (see Fleet Operation).

**The two inputs that must not come from the LLM.** `activity` is a *structural* label supplied by
the orchestrator (which node in the DAG is running), never parsed from model output — same principle
as `agent_id` in Component 3. And the *policy* (`tier_map`, `activities`) is construction-time config
injected by the launcher, exactly like the cost caps. The only thing the agent/router supplies is the
*requested* `model` — precisely what the guard is there to bound. Because the policy is not
LLM-derived, this needs **no** dependency on the `[D1]` identity decision: like `CostGovernor`, the
launcher constructs it with the right policy for the run. (At fleet scale the policy is selected per
cohort from the manifest, so it inherits identity there the same way everything else does.)

**Call-site ordering.** Model first, then budget: `model_policy.check(activity, model)` →
`cost_governor.pre_call(est_tokens)` (the token estimate depends on the chosen model) → the call. A
rejected tier never reaches the token estimator.

**Downgrade is compliance, not evasion.** A raised `ModelPolicyError` *may* be handled by the router
choosing a compliant lower model and retrying — that is routing selecting a legal option. What is
forbidden (the skill's standing rule: never route around a raised `HarnessError`) is catching the
error and re-calling with the *same* over-tier model, or widening the policy at runtime. Record the
intervention either way.

**Composes with, does not replace, the spend cap.** `ModelPolicy` bounds per-call
*capability/unit-cost*; `CostGovernor` bounds *cumulative* spend and action counts. An agent can stay
under the frontier ceiling and still blow the dollar cap by looping — both guards fire independently.

**Still to specify:** the tier taxonomy and provider→tier map (`[D8]`, couples to `[D3]`); the
empirical benchmarking that sets *which* activities can sit at WEAK without quality loss (this is the
"what 'smallest capable model' means per task type" open item from Component 5, now owned here); and
whether an unmapped-but-newer model of a known family resolves by prefix or stays fail-closed
(default: **fail-closed** — an unmapped model is an ungoverned model).

**Real-world gap found dogfooding (2026-08-10, novamart-pipelines).** The first live caller
(`agentic_incident_memory_v2.py`) exposed a drift risk the primitive itself doesn't prevent:
`ModelPolicy.check()` is only ever invoked from a DAG-parse-time helper (`enforce_model_policy()`)
fed a **hand-maintained dict** that is supposed to mirror each task's actual `model_id=` kwarg on
its `@task.agent`/`@task.llm_branch` decorator — but nothing ties the two together. Someone can
bump a task's real `model_id` without touching the dict, and the parse-time check keeps passing
while the task silently runs over-tier. Fix (not yet built): collapse to one source of truth by
checking **at the declaration site** instead of against a separately maintained mirror — a small
wrapper that takes `(activity, model_id)`, calls `policy.check()` inline, and returns the
(validated) `model_id` for the decorator to consume directly:

```python
def guarded_model(activity: str, model_id: str) -> str:
    _POLICY.check(activity, model_id)
    return model_id

@task.agent(..., model_id=guarded_model("investigate_aws", MODEL_WEAK))
```

Same parse-time-fail behavior as today, but drift becomes structurally impossible instead of just
unlikely. This is about how callers *invoke* `check()`, not a change to `model_policy.py` itself —
worth folding into the `agent-harness` skill's guidance next to the existing call-site-ordering
rule, so future callers get it right the first time instead of rediscovering it.

**Multi-provider `tier_map` (Gemini) — sharpens `[D8]`.** The primitive is already
provider-agnostic (`tier_map: dict[str, Tier]` accepts any concrete model string), so no code
change is needed in `model_policy.py` itself. What's actually needed: concrete pydantic_ai Gemini
model-id strings per tier (e.g. `google-gla:gemini-*-flash` / `-pro` — exact naming TBD), added
alongside the existing Anthropic entries in the caller's `tier_map`, and a decision on whether a
given activity's band should admit Claude-only, Gemini-only, or either at a tier. This is squarely
`[D8]`'s "concrete provider→tier map," which already waits on `[D3]`'s provider answer — novamart's
own live `ANTHROPIC_API_KEY` usage answers `[D3]` for Claude, but Gemini *API* access (vs. just a
Workspace subscription) is still unconfirmed; don't spend time on exact Gemini model strings until
that's checked.

### Violation response: reject vs. clamp-and-continue — `[D9]`

Today a violation always raises `ModelPolicyError`, and the call — or, for
`agentic_incident_memory_v2`, the entire DAG parse — fails closed. For some activities we may
instead want the harness to **substitute a compliant model and continue** rather than stop the run
outright: a misconfigured `model_id` shouldn't necessarily block an entire incident response if a
safe fallback exists.

This is a different mechanism from **"Downgrade is compliance, not evasion"** above, and the two
should not be conflated: that paragraph describes the *caller* catching a raised error and retrying
with a compliant model — routing selecting a legal option after a rejection. Clamp-and-continue is
the *harness itself* substituting a model **without ever raising**, which needs a stronger
guarantee than a caller's own retry, since there is no exception boundary forcing the substitution
into view.

**This is a real change in what "enforce, not route" means, and needs to be decided deliberately,
not fallen into.** The line drawn earlier in this section — the harness caps, the launcher/router
picks — is *why* the cap can't be reasoned around. Silently substituting a different model when a
request violates the band means the harness itself is now making a routing decision. That's not
disqualifying, but it must be an explicit, **opt-in posture per activity**, not a global behavior
swap: `ActivityBand` gains an `on_violation: Literal["reject", "clamp"] = "reject"` field (name
TBD), defaulting to today's behavior everywhere until an activity opts in.

**Only the ceiling direction is in scope for now.** Clamping *down* to the highest tier still
inside `max_tier` only ever **reduces** spend — consistent with the ceiling already being framed as
a cost/blast-radius guarantee above, and safe to build first. Clamping *up* to satisfy a hard
`min_tier` floor **increases** spend the caller never asked for and can interact badly with
`CostGovernor`'s cumulative caps — deferred, not rejected; needs its own justification before it's
built.

**Non-negotiable: every clamp is a `harness_intervention` audit event, never a silent
substitution.** An automatic downgrade that keeps an over-tier call from failing the run is
strictly better than uncapped spend — but it is still the harness doing something other than what
was asked, and that is exactly the kind of event the audit trail exists to surface, not hide. Two
implementation details this forces:
- `AuditLog.record_intervention()` defaults `decision="denied"`, which is wrong for a clamp (the
  call *proceeded*, just on a different model) — the call site must pass an explicit `decision`
  (e.g. `"allowed"`) alongside the intervention record, or the trail will misreport clamped calls
  as rejected.
- `Intervention.prevented` should name both models (e.g. `"clamped investigate_aws from
  claude-sonnet-5 to claude-haiku-4-5"`), not just that a clamp happened, so
  `demo_harness_report.py`'s existing per-component tally stays meaningful once `model_policy`
  becomes one of the counted components.

**Still open:** the exact `ActivityBand` field shape; whether `check()` gains a second method
(e.g. `resolve()`, returning the possibly-substituted model) or the existing method grows a mode
branch; and whether clamp-eligible activities need their own risk-tier ceiling (e.g. never offered
for VERY HIGH-tier activities like `propose_code_fix`, only for LOW/MEDIUM). Not blocking current
build — no caller needs this yet; captured here so the next concrete use case has a starting design
instead of re-deriving it.

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
- Append-only storage via a **pluggable, warehouse-agnostic writer** (client warehouse preferred;
  SQLAlchemy MySQL/Postgres fallback; local JSONL for the demo) — see **Fleet Operation** and `[D4]`
- Structured events with a consistent schema: `{agent_id, action, inputs, outputs, ts, user,
  decision}`, plus the fleet fields `{event_type, intervention, incident_id, cohort, job_id}` that
  separate **harness interventions** from **in-band agent actions** (see Fleet Operation)
- Queryable for forensic reconstruction — "what did the agent do between 14:00 and 14:30?" and, at
  fleet scale, "how often did the harness intervene this week, and on which jobs?"
- HITL decision (who approved, what they saw, when) stored alongside the action

---

## Components Are Opt-In at the Call Site

The harness does **not** wrap every LLM call identically.
- **Always-on:** Components 1 (input wrapper), 2 (output validator), 5 (cost governor — and its
  **Model-Tier Policy** extension, wherever a step selects among models).
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
Jira tickets. Minimum: Components 1, 2, 3, 5, 6, 8 + audit trail. Its **model-tier bands** (Component
5 extension) are the demo's showcase for this feature: investigation at MID, ticket/Slack/status
steps capped at WEAK.

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

## Fleet Operation — Multiple Concurrent Agents

Raised by Scott Mitchell in the 2026-06-19 team meeting: how does this work when a client has us
put agents in place across many jobs — e.g. monitoring 100 Airflow jobs? One agent for all 100?
One per job? Groups? And how do we *see* what happens across the fleet — in particular, when the
**harness stepped in** vs. when the **agent handled the issue itself**? This section is the answer.
Treat the topology and audit-schema parts as decided-in-principle and the manifest/inheritance
details as a proposal pending iteration with Scott.

> **High-level pre-read:** [`docs/fleet_design.md`](docs/fleet_design.md) is the shareable,
> plain-language version of this section (written for a non-engineering read). Keep the two in
> sync — this section is the engineering source of truth; the doc is the summary.

### "Agent" is three units, not one

The "1 vs 100" question conflates three independent things. Separate them and the tension dissolves:

- **Work unit** — an Airflow job/DAG. Fixed by the client (100 of them).
- **Governance scope** — an `agent_id`: the key that access controls, cost caps, and audit
  attribution hang off. This is the unit of **blast radius and least privilege**.
- **Reasoning invocation** — one harness-wrapped LLM call. The only thing that costs money.

Nothing forces these to be 1:1:1.

### Topology: watcher tier + per-cohort reasoning

**Do not run 100 always-on LLM agents, and do not run one agent holding the union of all 100 jobs'
permissions.** Instead:

- **Watcher tier (1:1 with jobs, ~free).** Airflow already runs the jobs and already fires
  `on_failure_callback` / SLA-miss / retry-exhausted hooks per task. That is the detection layer —
  deterministic, zero LLM cost, scales arbitrarily. This is step 1 of the cost waterfall ("can a
  deterministic rule answer this? → use it") applied to detection. No LLM idles on a healthy job.
- **Reasoning tier (invoked per incident).** When a watcher escalates, it invokes a harness-wrapped
  reasoning agent under a **cohort `agent_id`**. Cost is per incident, not per job-hour: a healthy
  fleet is nearly free; you pay when something actually breaks.

This removes the cost objection to per-job agents (no idle LLMs) **and** the blast-radius objection
to a single agent (no identity with union-of-everything permissions).

### How many agent identities? Group by `(risk tier × system/credential scope × owner)`

Not 100, not 1. The agent identity is **the unit over which you are willing to share a blast radius
and a least-privilege scope** — not the unit of work. Jobs that touch the same systems, carry the
same risk tier, and belong to the same team share one `agent_id`; jobs that differ in *what they can
touch* or *how dangerous they are* must not. In practice 100 jobs collapse to **~5–15 cohort
identities** (e.g. `finance-tier-HIGH`, `marketing-readonly-LOW`, `platform-tier-MEDIUM`), each with
a tight allowlist instead of the union of all 100 jobs' permissions.

### Configuration & management at fleet scale

~12 cohorts is manageable; hand-authoring 12 near-identical `agents/<name>/` dirs (let alone 100) is
not. Two additions to the per-agent config layout:

1. **Fleet manifest** — one version-controlled file mapping `job → cohort → agent_id`. This *is* the
   management surface: the whole topology reviewable and diffable in one place. Adding or moving a job
   is a manifest edit.
2. **Config inheritance** — org defaults → cohort template (by risk tier) → per-cohort override.
   Author one HIGH-tier template, not twelve copies. (omnigent's stacked server > agent > session
   policy scopes are precedent that layered policy is the right shape.)

This **sharpens `[D1]`**: at fleet scale, identity is "the launcher assigns `agent_id` from the
manifest," which favors the env-var-set-by-launcher option over a per-agent signed token, and means
D1 must be decided with the manifest in mind. Fleet operation raises D1's urgency.

### Aggregate audit: separating "harness intervened" from "agent handled it"

This is the core observability requirement. Every event must be classifiable as one of:

- **In-band** — the agent reasoned and acted *within* its bounds (diagnosed, escalated normally,
  resolved). The agent doing its job.
- **Intervention** — a control *fired* (cost cap, loop guard, tool-permission denial, output-validator
  rejection, HITL block, kill switch). The harness changed what would otherwise have happened.

The components already raise exceptions and the *call site* logs through the audit log, so the
exception boundary is exactly where an intervention is stamped. Extend the audit schema (currently
`{agent_id, action, inputs, outputs, ts, user, decision}`) with:

| Field | Purpose |
|---|---|
| `event_type` | `agent_action` / `harness_intervention` / `hitl_decision` / `evaluator_flag` — the in-band vs. intervention split |
| `intervention` | on interventions: which component fired and what it prevented (e.g. `cost_governor: capped messages_sent at 20`, or `model_policy: blocked FRONTIER on file_ticket (max WEAK)`) |
| `incident_id` | correlation/trace id stitching one incident across watcher → reasoning → tool calls → interventions → HITL → resolution |
| `cohort`, `job_id` | fleet attribution — which cohort/job an event belongs to |

`incident_id` is what turns interleaved multi-agent streams into reconstructable stories. With it:

- **Per incident:** "Job X failed → `finance-HIGH` agent diagnosed → tried 50 Slack msgs → cost
  governor capped at 20 → escalated to human → approved rollback."
- **Aggregate (week):** "312 incidents across 100 jobs; agents handled 280 in-band; harness intervened
  32× (18 cost caps, 9 loop guards, 5 HITL rejections)." Where model bands are set, "N model-tier
  blocks" joins that line — and a *recurring* block on one activity is the signal that its band is
  mis-set, exactly the false-positive-label case below.

The **harness intervention rate is a product metric** — the empirical measure of how often the harness
earned its keep, and a strong Summit/client artifact ("over 30 days the harness caught N runaway loops
and M over-budget excursions before they reached your Slack/Jira/warehouse"). Trend it: rising = agents
degrading or limits too tight; falling = trust increasing.

**Interventions need a post-hoc label.** Not every intervention is a good catch — some are false
positives (limit too tight, agent was fine). Support a label (human review, or the evaluator labels a
sample) so "32 interventions" doesn't read as all-good or all-bad, and feed it back into limit tuning.

### Audit backend: warehouse-agnostic, pluggable — `[D4]`

Per-run local JSONL cannot answer any of the cross-agent queries above; fleet monitoring needs a
shared, append-only, *queryable* store. **The store must be flexible to the client's stack** — we
write to whatever warehouse the client already runs (Snowflake, BigQuery, Redshift, …) so the audit
data lands where their broader analytics already live. That co-location is the *preferred* outcome:
the audit log was always specced as a first-class data product, and putting it in the client warehouse
lets it join the rest of their analytics.

Therefore the audit writer is a **pluggable backend behind one append-only interface**, not a single
technology:

- **Preferred:** the client's existing warehouse (Snowflake / BigQuery / Redshift) — audit data joins
  their analytics.
- **Portable fallback:** a small dedicated SQL DB (MySQL / Postgres) via **SQLAlchemy**, for clients
  without a suitable warehouse or where we want the agent audit isolated. SQLAlchemy keeps the writer
  engine-agnostic so the same code targets Postgres, MySQL, Snowflake, or Redshift.
- **Demo / local:** append-only JSONL (already built) — no infra.

So `[D4]` is a *pluggable-writer* decision, not a single-vendor pick: build one append-only writer
interface; select the engine per engagement. The fleet dashboard is then plain SQL over the audit
table regardless of engine — QBiz's wheelhouse, and a clean dogfooding story (we monitor your agents
with the same warehouse tooling we sell you).

### Relationship to Deferred Concerns

This section addresses **concurrent, independent** fleet operation (Deferred Concern #4 observability,
now design-led rather than parked). It does **not** resolve **agent-to-agent composition** (#1 — the
trust model when agent A *calls* agent B): that stays deferred until we actually chain agents.
Concurrent ≠ chained.

---

## Data Sensitivity Classification & Data-Level Guardrails

> **Consumer-driven (2026-07-08).** The `qbiz_dbt_startup_kit` — a dbt kit built
> to be driven by AI agents — needs the harness to stop a consultant from
> *accidentally exposing sensitive data through an AI* (e.g. an agent that
> summarizes a table and sweeps a PII column into a Slack post). Full design lives
> in that repo's `docs/DATA_SENSITIVITY_PROPOSAL.md` (pending team sign-off). This
> section records what the harness must do to support it — **including
> capabilities not yet specced above** — so the need is visible from the harness
> side. Nothing here is built.

**Client policy overrides the QBiz baseline.** As everywhere in the QBiz stack, a
client's own data-classification and security protocols take precedence. The QBiz
taxonomy (`public` / `internal` / `confidential` / `restricted` + PII/PHI/PCI
categories) is a **good default baseline**, most valuable for clients with no
policy of their own. The harness must therefore treat the classification scheme
**and its enforcement thresholds as configuration** (per-engagement, overridable),
never hardcoded — same posture as `limits.yaml`.

**The model:** the data producer (the dbt kit) *declares* per-object sensitivity
as metadata (in dbt `manifest.json` / `catalog.json`); the harness *enforces* it.
Per the dependency rule, the harness imports nothing from the kit — the agent
feeds kit-derived classification into the controls at its call site.

### Desired features (several not yet specced above)

| # | Capability | Relationship to current spec |
|---|---|---|
| **J1** | **Data-object access control by clearance** — deny an agent reads of tables/schemas/columns above its sensitivity clearance (e.g. a LOW read-only agent cannot touch any `restricted` model or the `silver_pii` schema). | **New / extends Component 3.** Component 3 today is *tool*-level allowlisting; this extends the same idea to *data-object*-level, keyed on classification. Sits on `[D1]` agent-identity. |
| **J2** | **Classification-aware redaction** — mask values of columns declared `restricted` before they enter the model context. | **Extends Component 1.** Component 1 already plans PII stripping *by detection* (regex/Guardrails); this adds stripping *by declaration* (trust the manifest's column classification) — far more reliable than pattern-matching. **Unblocked; natural first increment.** |
| **J3** | **Classified-data leak detection in output** — block agent output containing values sourced from `restricted` columns. | **Extends Component 2** (which flags out-of-scope *systems* today) to out-of-scope *data*. |
| **J4** | **Classification in the audit schema** — record the sensitivity level/category of data each action touched, so "did any agent touch PII this week?" is queryable at fleet scale. | **New audit fields** — not in the current `{agent_id, action, …, event_type, intervention, incident_id, cohort, job_id}` schema. Additive. |
| **J5** | **Classification-driven auto risk-tiering** — an agent whose reachable data includes `restricted`/PII is automatically HIGH+ (VERY HIGH if regulated), pulling in evaluator + HITL + red-team gates. | **Mechanizes Risk Tiering** — today the tier is assigned by judgment; this derives a *floor* from the data in scope. |
| **J6** | **Classification provider/loader** — a shared interface the above consult to resolve an object's classification at runtime (from the dbt manifest/catalog, or a dbt MCP surface). | **New shared infrastructure.** Source is an open decision — see `[D7]`. |

**Fail-safe posture:** default-deny / default-redact when an object's
classification is missing or ambiguous — unclassified is treated as `restricted`,
never waved through.

**Dependencies & sequencing:** J1 and J5's enforcement sit on `[D1]`
agent-identity, so this **raises D1's priority**. **J2 (redaction) is unblocked**
and is the sensible first deliverable. `[D7]` settles the classification source.

---

## Quality Gates

### Gate 1 — Automated Checks (runs on every build, blocks deployment on failure)

- Unit tests for every tool (input/output contract)
- Linting and type checking of all harness code
- Access control verification — explicitly test that the agent *cannot* call tools outside its allowlist
- Hard limit enforcement — test that cost/token governors fire at the configured threshold
- Audit logging validation — confirm every action type produces a log entry
- Tool schema consistency — MCP schema matches actual Python function signatures
- **Model-tier enforcement** — the checks-and-balances suite for `model_policy.py`:
  - **Ceiling is hard:** a request one tier above `max_tier` raises `ModelPolicyError` *before* any
    API call; a request at or below `max_tier` passes.
  - **Floor when hard:** a request below a `floor_hard` activity's `min_tier` raises; at/above passes.
    A soft floor does *not* raise (it is a default, not a boundary).
  - **Cross-provider parity:** `claude-haiku-*` and `gemini-flash-*` both resolve to `WEAK`, so a
    `max_tier: WEAK` band admits either and a `MID` step rejects both providers' frontier models —
    proving the band is provider-agnostic, not Claude-specific.
  - **Fail-closed on the unknown:** an unmapped model string, and an unmapped `activity`, both raise
    (an ungoverned model/activity is never silently allowed).
  - **Policy is not LLM-widenable:** the guard reads only construction-time `tier_map`/`activities`;
    a test confirms no input-/output-derived value can raise the effective ceiling (immutable policy).
  - **`activity` is structural:** the label the guard keys on comes from the orchestrator, asserted
    in the reference wiring — never from model output.
  - **Evaluator different-model rule stays satisfiable:** config-time validation fails a cohort whose
    band for an evaluated activity admits only one concrete model (Component 7 requires the evaluator
    to be a *different* model than the primary — an over-tight band that makes that impossible is a
    build error, not a runtime surprise).
  - **Call-site order + audit:** in the reference wiring `model_policy.check` runs before
    `cost_governor.pre_call`, and a rejection emits exactly one `harness_intervention` audit event
    with `component=model_policy` and the `prevented` detail; an allowed call emits none.

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
│   │   ├── model_policy.py         # Component 5 extension — per-activity model-tier cap
│   │   ├── orchestration.py        # Component 6
│   │   ├── hitl.py                 # Component 8
│   │   └── audit.py                # cross-cutting audit log
│   └── tests/                      # Gate 1 lives here
├── agents/                         # per-agent config (no harness code changes)
│   ├── fleet.yaml                  # fleet manifest: job → cohort → agent_id (see Fleet Operation)
│   ├── _defaults.yaml              # org-wide policy defaults (inherited by all cohorts) — incl. model tier_map [D8]
│   ├── _templates/<risk_tier>.yaml # cohort templates by risk tier (inherited + overridden) — incl. default model bands
│   └── <cohort_name>/              # per-cohort overrides
│       ├── permissions.yaml        # which tools this cohort can call
│       ├── limits.yaml             # token budget, spend cap, retry limits, timeouts
│       ├── models.yaml             # per-activity model-tier bands (min/max/floor_hard) — Component 5 ext.
│       ├── evaluator_rubric.md     # Component 7 adversarial prompt
│       └── AGENTS.md               # agent identity, scope, operating rules (versioned)
└── mcp/                            # existing MCP servers (Slack, Astro/Airflow, …)
```

Reminder: **agents import `qbiz_harness`; the harness imports nothing from `agents/` or `mcp/`.**

---

## Implementation Order

Phases are ordered by what unblocks what. Each phase lists its **prereqs** (what must exist first)
and any **blocker** (a decision in *Required Decisions* below that gates it). Decisions are
referenced as `[D#]`. Gate 1 tests are written *with* each component, not deferred to the end.

### Phase 0 — Scaffold ✅ DONE (PR #2)
- [x] `harness/` package — `pyproject.toml`, `src/qbiz_harness/`, `tests/`
- [x] `qbiz_harness.exceptions` — the `HarnessError` hierarchy every component raises through
- [x] Smoke tests (seed of Gate 1) + README + `HARNESS_PLAN.md`

### Phase 1 — Foundational, agent-agnostic components (no blockers)
These need no pending decision and no per-agent input — build now, in any order.
- [x] **Component 5 — Cost & Compute Governors** (`cost_governor.py`): token/spend caps,
      action-count limits, kill switch, redundancy detection. Fully specified. *Done — Gate 1
      threshold tests in `tests/test_cost_governor.py`.*
- [x] **Component 6 — Orchestration Controls** (`orchestration.py`): retry/backoff, loop guard,
      fallback paths. Engineering detail to settle in-code: per-tool timeouts (not a blocker).
      *Done — per-call timeout is a call-site arg; tests in `tests/test_orchestration.py`.*
- [x] **Component 5 extension — Model-Tier Policy** (`model_policy.py`): provider-agnostic
      `Tier` ordinals + per-activity `ModelPolicy.check(activity, model)`; new `ModelPolicyError` on
      the `HarnessError` hierarchy. Agent-agnostic and **unblocked** — like `CostGovernor`, the
      launcher constructs it with config; needs no `[D1]`. The *primitive* ships here; the concrete
      tier taxonomy/provider map is `[D8]` (couples to `[D3]`) and the per-cohort bands are authored
      in Phase 7. *Done — hard ceiling always enforced, floor enforced only when `floor_hard=True`;
      construction-time validation that a `requires_multi_model` activity's band admits more than
      one concrete model; Gate 1 tests in `tests/test_model_policy.py` (14 cases: ceiling, floor,
      cross-provider parity, fail-closed on unmapped model/activity, policy not runtime-widenable,
      evaluator-band validation, reference call-site ordering + audit).*
- [x] **Cross-cutting Audit Log** (`audit.py`): structured append-only event writer. Everything
      below logs through it, so build it here. Demo can use local append-only JSON; production
      storage backend is `[D4]` and not needed yet. *Done — local JSONL; tests in
      `tests/test_audit.py`. Components stay pure; the call site logs through it.*
- [x] **Component 8 — Human Checkpoints** (`hitl.py`): wraps the Slack MCP's blocking
      `request_approval` (channel, prompt, timeout_seconds, thread_ts) via an injected
      `ApprovalTransport` protocol — no MCP import, per Decision Locked #3. Per-agent timeout
      *policy* `[D6]` (fail-closed / fail-open / escalate) is an enum arg defaulting to
      fail-closed; escalate raises `HitlEscalationRequired`. *Done — returns a structured
      `ApprovalDecision` the call site logs through `AuditLog`; tests in `tests/test_hitl.py`.*

### Phase 2 — I/O screening components
- [ ] **Component 1 — Input Wrapper** (`input_wrapper.py`): PII strip, injection screen, rate
      limit, safety inject. *Prereqs:* per-agent PII type definitions + injection-screening
      dependency choice `[D5]`. Regex-only screening can ship first; Guardrails/Rebuff added later.
- [x] **Component 2 — Output Validator** (`output_validator.py`): format check, hallucinated-tool
      block, out-of-scope flag. *Prereq:* the per-agent tool allowlist (shared with Component 3).
      *Done — pure Layer-1 checks raising `OutputRejectedError`; each check opt-in at the call site.
      `check_format` is a lightweight `{field: type}` schema (JSON-string parse, bool-not-int guard),
      not full JSON-Schema — a richer contract is a later dependency choice. Partial-output policy
      realized as two entry points: `validate_output` (raises → reject-and-re-prompt) and
      `inspect_output` (returns `ValidationResult` of `Violation`s → strip-and-log). Factual
      consistency + deep semantics deferred to the evaluator (Component 7). Tests in
      `tests/test_output_validator.py`.*

### Phase 3 — Tool access controls — **BLOCKED on `[D1]`**
- [ ] **Component 3 — Tool-Level Access Controls** (`access_controls.py`). Cannot start until the
      agent-identity injection mechanism `[D1]` is decided — identity is the foundation the whole
      permission map keys off. Shares the per-agent tool allowlist with Component 2.

### Phase 4 — Memory scoping — **CONDITIONAL on `[D2]`**
- [ ] **Component 4 — Memory Scoping** (`memory.py`). Only built **if** agents share a memory
      backend `[D2]`. If memory is per-agent, this phase is skipped entirely.

### Phase 5 — Evaluator — **BLOCKED on `[D3]`, build last**
- [ ] **Component 7 — Evaluator Agent**: a *different* model than the primary reviews output.
      Blocked on the provider/evaluator-model decision `[D3]`, and deliberately last because rubric
      quality depends on seeing real agent outputs to know what to evaluate against.

### Phase 6 — Gates
- [ ] **Gate 1** (automated): written per-component as each lands (access-control denial tests,
      governor-threshold tests, audit-coverage tests, schema/signature consistency).
- [ ] **Gate 2** (evaluator): run against real Agentic Incident DAG scenarios. Depends on Phase 5,
      therefore on `[D3]`. Soft target for the Airflow demo; **required before any client engagement.**
- [ ] **Gate 3** (human red team): post-demo unless the demo is client-facing.

### Phase 7 — Fleet operation (design-led; near-term audit tagging)
Direction set 2026-06-19 (Scott Mitchell). See **Fleet Operation** for the full design.
- [x] **Audit tagging (near-term, no blocker):** add `event_type`, `intervention`, `incident_id`,
      `cohort`, `job_id` to the `audit.py` event schema and stamp interventions at the call-site
      exception boundary. Doable now against the existing JSONL writer; unlocks the
      in-band-vs-intervention view before any backend swap. *Done — `EventType` str-enum,
      `Intervention(component, prevented, label)` + `InterventionLabel` (post-hoc good-catch /
      false-positive), all fields additive/optional on `AuditEvent`. `AuditLog.record_intervention(...)`
      is the call-site exception-boundary helper; `interventions()`, `by_event_type()`,
      `by_incident()`, and `intervention_counts()` (drives the "18 cost caps, 9 loop guards"
      dashboard line) query it. Tests in `tests/test_audit.py`.*
- [ ] **Pluggable audit writer `[D4]`:** one append-only writer interface; engine selected per
      engagement (client warehouse preferred; SQLAlchemy MySQL/Postgres fallback; JSONL for demo).
- [ ] **Fleet manifest + config inheritance:** `agents/fleet.yaml` (job → cohort → agent_id) plus
      org-defaults → cohort-template → per-cohort-override resolution. Couples to `[D1]`
      (launcher-assigned identity from the manifest).
- [ ] **Per-cohort model bands + tier taxonomy `[D8]`:** the org `tier_map` in `_defaults.yaml`,
      default bands in the risk-tier templates, and per-activity overrides in each cohort's
      `models.yaml` — resolved through the same inheritance chain as everything else. Needs the
      `model_policy.py` primitive (Phase 1) and the taxonomy decision `[D8]`. The empirical
      benchmarking that fixes *which* activities are safe at WEAK feeds these values.
- [ ] **Watcher tier:** wire Airflow `on_failure_callback` / SLA-miss hooks to invoke a
      harness-wrapped reasoning agent per incident under its cohort `agent_id`.

---

## Required Decisions

These gate the phases above. The first two are **team decisions** (external dependency); the rest
are **ours to make** at build time.

**Two deadline classes — keep them distinct:**
- **Soft target — the Airflow demo.** Full LLM-interaction capability (the evaluator and the demo
  driver, i.e. `[D3]`) is a *nice-to-have* for the Airflow Summit demo. If it isn't working by
  then, that's fine — the demo can show the harness mechanics without the full live-LLM loop.
- **Hard requirement — any client engagement using the MCP servers.** Before *any* client work on
  the MCP servers, the full-functionality decisions **must** be closed — `[D3]` (LLM provider +
  evaluator model) above all, plus `[D1]` since a client-facing agent is HIGH+ and needs the
  access-control layer. There is no "ship to a client without these" path.

| ID | Decision | Blocks | Needed by | Type / status |
|---|---|---|---|---|
| **D1** | **Agent-identity injection** — env var (set by launcher) vs. signed token at harness init. Never read from LLM output. Fleet operation favors *launcher-assigned-from-manifest* (see **Fleet Operation**). | Component 3 (Phase 3) — entire access-control layer; also the fleet manifest (Phase 7) | Before Phase 3. **Hard requirement before any client engagement** (client-facing agents are HIGH+ and need Component 3). | Team. *Pending review.* |
| **D2** | **Shared vs. per-agent memory backend** — does any agent share memory with another? | Component 4 (Phase 4) — whether it's built at all | Before Phase 4. Low urgency; **default to per-agent (skip Component 4)** until a shared backend is actually introduced. | Team. *Open; safe default exists.* |
| **D3** | **LLM provider + evaluator model** — Qbiz may lack an Anthropic key; Gemini possible. Evaluator must be a *different* model than the primary, so this picks both. Also gates the demo driver `incident_demo.py`. | Component 7 (Phase 5) + Gate 2 + demo driver | **Soft target: the Airflow demo** (fine if not ready). **Hard requirement before any client engagement** using the MCP servers. | Team. *Pending — see project memory `llm_provider_open_question`.* |
| **D4** | **Audit storage backend (HIGH+)** — *pluggable, warehouse-agnostic writer*, not a single vendor. Preferred: client's existing warehouse (Snowflake / BigQuery / Redshift) so audit joins their analytics; portable fallback: small MySQL/Postgres via SQLAlchemy; demo: local JSONL (built). See **Fleet Operation**. | Production-grade audit **and all fleet aggregate monitoring** | Before any HIGH+ production deploy or any multi-agent client engagement. Demo uses local JSONL. | Ours. *Promoted by the fleet direction (2026-06-19); build one writer interface, pick the engine per engagement.* |
| **D5** | **Injection-screening dependency** — regex-only vs. Guardrails AI vs. Rebuff. | Full Component 1 (Phase 2) | At Phase 2. Ship regex-only first; add a library later if needed. | Ours. *Decide at build time.* |
| **D6** | **HITL timeout policy (per agent)** — fail-closed / fail-open / escalate. | Per-agent config, **not** the Component 8 mechanism | At each agent's config time. **Default fail-closed for HIGH+.** | Ours. *Per-agent, default exists.* |
| **D7** | **Data-classification source & data-level access-control scope** — where the harness reads per-object sensitivity at runtime (dbt `manifest.json` / `catalog.json` `meta` vs. a dbt MCP surface), and how far data-object access control (J1) extends (schema / table / column). Client policy overrides the QBiz baseline taxonomy. | J1–J6 (data-sensitivity guardrails); sharpens `[D1]` | Before building data-level guardrails; consumer (`qbiz_dbt_startup_kit`) is waiting on it. See **Data Sensitivity Classification** above. | Team + ours. *New (2026-07-08); design in that kit's `docs/DATA_SENSITIVITY_PROPOSAL.md`.* |
| **D8** | **Model-tier taxonomy + provider→tier map** — the concrete `WEAK/MID/FRONTIER` bands and which model IDs map to each (couples to `[D3]`: the provider list depends on whether we run Claude, Gemini, or both). Also: default soft vs. hard floor per risk tier. | Per-cohort model bands (Phase 7). **Not** the `model_policy.py` primitive (Phase 1), which is taxonomy-agnostic. | At Phase 7 config authoring. The primitive ships without it; bands can start conservative (everything MID) and tighten as benchmarking lands. | Ours, but *waits on `[D3]`'s provider answer* for the concrete map. *Safe default: everything MID until benchmarked.* |
| **D9** | **Model-policy violation response** — hard reject (current, all activities) vs. an opt-in per-activity clamp-to-nearest-compliant-tier with mandatory audit-intervention logging. Ceiling-clamp (reduce spend) only in scope; floor-clamp (increase spend) deferred as higher-risk. | `ActivityBand`/`ModelPolicy.check()`'s API shape for any activity that wants clamp-and-continue. | Whenever a concrete use case needs continue-not-fail instead of DAG-parse failure; not blocking current build. | Ours. *Open — see Component (extension of 5) § "Violation response: reject vs. clamp-and-continue."* |

**The two that actually pace us are D1 and D3** — both are team decisions and both are on the
critical path to *client* work (not the demo, which can proceed without full LLM capability). D2
and D4–D6 either have a safe default or are made at build time, so they don't block progress. Get
D1 and D3 in front of the team well ahead of the first client engagement — and before Phase 3
starts, since D1 gates it.

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

1. **Multi-agent harness composition** — when agent A *calls* agent B, what is the trust model?
   Does B's harness fire independently? If A is compromised, can it pass malicious inputs that
   bypass B's input wrapper? Decide when we first chain agents. (*Concurrent, independent* fleet
   operation is now designed — see **Fleet Operation**; this concern is specifically agent-to-agent
   *chaining*, which remains deferred. Concurrent ≠ chained.)
2. **Separate-repo extraction** — only when a non-agent consumer needs the harness without the
   whole repo, or audit access must be narrower than repo write access. Cheap to do later given
   the one-way dependency rule.
3. **Harness versioning & migration** — running old and new harnesses in parallel for comparison
   across a model-generation change. Revisit at the first such migration.
4. **Observability spec** — **now design-led, not parked (2026-06-19):** the fleet audit schema
   (`event_type` / `intervention` / `incident_id`) and the harness-intervention-rate metric in
   **Fleet Operation** are the core of this spec. Still to spec: alert thresholds and the
   "behavioral drift" signal; LangSmith / Arize remain candidate COTS tools.
5. **Harness security / supply chain** — the harness is itself the enforcement boundary. Who
   audits it, how often, and dependency-pinning for Guardrails AI et al. Pairs with the
   `CODEOWNERS` decision — both trigger when code reaches client hardware.
6. **`CODEOWNERS` / restricted write** — see Decision 4. Valid approach once this lands on client
   hardware; open to all consultants until then.
