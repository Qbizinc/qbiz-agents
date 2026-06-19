# Fleet Design — Running the Harness Across Many Agents

**Purpose:** a pre-read for the next harness discussion. It answers the questions Scott raised in
the 2026-06-19 meeting about what changes when we move from a one-off agent to many agents running
at a client, and proposes a direction we can react to together.

**Audience:** anyone shaping the harness direction. High-level by design — the engineering detail
lives in [`../HARNESS_PLAN.md`](../HARNESS_PLAN.md) § *Fleet Operation*.

---

## The questions on the table

From the meeting, the concrete scenario: **a client has us put agents in place to monitor 100
Airflow jobs.**

1. How does that actually work — **one** agent for all 100? **One per job**? Some number **in
   between**?
2. How do we **configure and manage** that without it becoming unmanageable?
3. How do we **see what's happening** — what breaks, and specifically **when the harness stepped in
   to stop something vs. when the agent handled the pipeline issue on its own**?

This doc takes each in turn, then names the open questions worth deciding as a group.

---

## The short answer

- **Not 100 agents, not 1.** Group jobs into a handful of **cohorts** (~5–15 for 100 jobs) by how
  dangerous they are and what they're allowed to touch. Each cohort is one governed "agent."
- **Reasoning runs on demand, not 24/7.** Airflow already detects failures for free; an LLM agent
  only wakes up when there's an actual incident. A healthy fleet costs almost nothing.
- **Every action is tagged** so we can tell, at a glance, the difference between *"the agent did its
  job"* and *"the harness had to step in."* That distinction is the headline of the whole monitoring
  story — and a number we can show a client.
- **The audit data goes wherever the client's data already lives** (Snowflake, BigQuery, Redshift,
  or a small Postgres/MySQL of our own as a fallback). We don't lock to one warehouse.

---

## One-off vs. fleet: the harness is the same, the *operating model* is not

The enforcement components (cost caps, HITL, audit, etc.) don't change between a single project
agent and a 100-agent rollout. What changes is everything *around* them — identity, config, and how
we read the logs. Worth being explicit so we right-size effort:

| | **One-off / small project** | **Fleet-scale rollout** |
|---|---|---|
| How many agents | 1, maybe a few | Many jobs → a handful of cohorts |
| Identity | Hardcoded / single env var | Assigned from a **manifest** at launch |
| Config | Hand-written per agent | **Templates + inheritance** (author once, reuse) |
| Audit | One log, read by eye | **Shared, queryable** store; read as aggregate |
| Monitoring | "Did this agent do its job?" | "How's the **fleet**? Where is the harness intervening?" |
| Cost | Negligible | Must avoid paying for idle agents |

The mistake to avoid is carrying one-off habits (one config file per thing, logs read by hand) into
fleet scale, where they break. The rest of this doc is about the fleet column.

---

## 1. How many agents? Separate three things that get conflated

The "1 vs 100" question feels hard because "agent" is doing three jobs at once. Pull them apart and
it gets easy:

- **The job** — an Airflow DAG. There are 100. Fixed.
- **The governed scope** — the identity that limits and permissions attach to. This is the unit of
  **blast radius**: if one goes wrong, how much can it touch?
- **The reasoning** — an actual (paid) LLM call. This is the only part that costs money.

Nothing requires these to line up 1:1:1. Our recommendation:

- **Detection is free and per-job.** Airflow already runs all 100 jobs and already fires a callback
  when one fails or misses its SLA. That's our trigger — no LLM sitting idle watching a healthy job.
- **Reasoning is per-incident and per-cohort.** When a job fails, the callback wakes a harness-wrapped
  agent under the right **cohort** identity. We pay when something actually breaks, not per job-hour.

**So: how many identities?** Group jobs into cohorts by *(risk level × what systems they can touch ×
who owns them)*. Jobs that are alike in danger and access share one cohort and one tight permission
set; jobs that differ don't. 100 jobs typically land at **~5–15 cohorts** — e.g. `finance-HIGH`,
`marketing-readonly-LOW`, `platform-MEDIUM`.

This avoids both failure modes: one giant agent that can touch everything (huge blast radius), and
100 agents that are a nightmare to configure and pay to keep alive.

---

## 2. Configuration & management

A handful of cohorts is manageable; hand-writing even a dozen near-identical config sets is not.
Two pieces solve this:

- **A fleet manifest** — a single, version-controlled file that says *which job belongs to which
  cohort*. This is the one place to see and review the whole layout; adding or moving a job is a
  one-line change.
- **Config inheritance** — org-wide defaults, then a template per risk level, then small per-cohort
  overrides. We write the "HIGH-risk" rules once and reuse them, instead of copy-pasting.

(Side note: the open question of *how an agent proves its identity* — so a prompt can't make an agent
claim to be a different, more-privileged one — gets easier here, because identity comes from the
manifest at launch, not from anything the model says.)

---

## 3. Seeing it: "harness intervened" vs. "agent handled it"

This was Scott's sharpest question, and it has a clean answer. Every recorded action is labeled as
one of two kinds:

- **In-band — the agent handled it.** It diagnosed the problem and acted *within* its allowed
  bounds: posted an update, opened a ticket, escalated normally. The agent doing its job.
- **Intervention — the harness stepped in.** A limit fired: it hit the spend cap, looped too many
  times, tried a tool it isn't allowed to use, or was paused for human approval. The harness changed
  what would otherwise have happened.

Because the harness enforces in code, it *knows* the moment it intervenes — so we can stamp that
distinction automatically, plus an **incident ID** that ties together everything from one event:
the failure, the agent's reasoning, the actions, any intervention, and the resolution.

That gives us two views:

- **Per incident (the story):** *"Job X failed → the finance agent diagnosed it → it tried to send 50
  Slack messages → the harness capped it at 20 → it escalated to a human → human approved a
  rollback."*
- **Across the fleet (the dashboard):** *"312 incidents this week; agents handled 280 on their own;
  the harness intervened 32 times — 18 cost caps, 9 runaway-loop stops, 5 human rejections."*

**The intervention rate is the metric that proves the harness earns its keep.** It's exactly the kind
of thing to put in front of a client (and at the Airflow Summit): *"over 30 days the harness caught N
runaway loops and M over-budget excursions before they reached your Slack, Jira, or warehouse."* One
caveat we should track honestly: not every intervention is a good catch — some are limits set too
tight. So interventions get a follow-up label (good catch vs. false alarm) that feeds back into
tuning.

---

## 4. Where the data lives — flexible, not locked in

Reading the fleet aggregate means the audit data has to be queryable, not scattered in local log
files. The principle: **we write to whatever data stack the client already runs** — Snowflake,
BigQuery, Redshift — so the agent audit lands alongside their broader analytics and can feed into it.
Where there's no suitable warehouse (or we want the agent audit kept separate), we fall back to a
small dedicated Postgres/MySQL database of our own. Either way it's one writer behind one interface;
we pick the engine per engagement. No single-vendor lock-in.

---

## Open questions for us to settle

Things this design *raises* that are worth a group decision (not blockers to starting):

1. **Cohort boundaries in practice.** Is *(risk × access × owner)* the right grouping, or do real
   client fleets cut differently (by schedule, by data domain, by SLA)?
2. **Watcher access.** The "detection is free" claim assumes we can hook Airflow's failure/SLA
   callbacks in the client's environment. If a client won't let us touch DAGs, detection shifts to
   API polling — still workable, but no longer free. Worth confirming per engagement.
3. **How much to build now vs. at first real client.** The action-tagging that powers the
   intervened-vs-handled view is small and unblocked — we could add it to the current demo to make
   the Summit story stronger. The manifest, inheritance, and warehouse writer are bigger and could
   wait for a concrete client.
4. **Default cohort count.** Is ~5–15 the right ballpark to socialize, or do we expect clients to
   want finer-grained isolation (and accept the management cost)?

---

*Detailed engineering version: [`../HARNESS_PLAN.md`](../HARNESS_PLAN.md) § Fleet Operation, plus
decisions `[D1]` (identity) and `[D4]` (audit backend).*
