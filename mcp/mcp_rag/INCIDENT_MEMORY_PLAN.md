# Incident Memory — RAG-Backed Recurrence Tracking for the Airflow Incident Demo

> **Scope note.** This documents the RAG-backed incident memory for a **standalone, MCP-driven demo
> agent** (multiple MCP servers connected over stdio to one agent loop). The **realized** integration
> for NovaMart runs the incident response **inside Airflow** and embeds the RAG engine as a *library*,
> not over MCP — see `novamart-pipelines/RAG_INCIDENT_MEMORY_PLAN.md`, which supersedes this for that
> project. Kept here because the multi-MCP-agent wiring is a reusable pattern in its own right.

## Overview

Give the Agentic Incident agent a **persistent memory of past incidents and the tickets they
opened**, backed by the [RAG MCP server](./RAG_PLAN.md). Two payoffs:

1. **Recurrence detection at diagnosis time** — before the agent reasons about a failure, it
   searches the incident memory. If the same pipeline failed the same way before, it surfaces the
   prior incident, its root cause, and the ticket that fixed it — instead of re-diagnosing from
   scratch.
2. **An accumulating institutional record** — every resolved incident is written back as a
   searchable record (symptom → root cause → fix → ticket), keyed by its Jira ticket, and
   **updated when the ticket closes** (resolution + time-to-close appended).

This is a **separate concern from the base RAG server** (which is a general document-retrieval
engine, deliberately domain-neutral). This plan is the *application* of that engine to the incident
workflow — it lives here so the RAG-shaped design sits next to `RAG_PLAN.md`, but the code changes
land in the demo driver and touch three MCP servers.

**Scope note:** the current [`incident_demo.py`](../mcp_slack/demo/incident_demo.py) uses a
*simulated* Jira step (a stand-in `NOVA-4127` link) and connects **only** the Slack MCP. This plan
makes Jira real and adds RAG, using the same stdio + `tool_runner` pattern already in the demo.

---

## What it demonstrates (the pitch)

The demo itself is one pipeline — too small to *show* recurrence — but the wiring makes the
scalability story concrete and demonstrable in miniature:

- **Recurring problems become lookups, not re-investigations.** First occurrence is expensive; the
  tenth is a search hit. MTTR trends down as the corpus grows.
- **Institutional memory survives staff turnover.** Tribal knowledge ("oh, that DAG always breaks
  when upstream changes the schema") becomes a queryable record the *next* on-call agent reads.
- **Recurrence is the signal for systemic fixes** — repeated hits on the same DAG/root cause is the
  evidence that says *stop patching, fix the upstream contract*.
- **It scales the human, not just the system.** One engineer can't hold the history of a thousand
  pipelines in their head; a searchable incident memory is what lets the same team cover a growing
  fleet.

Honest framing to keep in the talk track: RAG gives *fuzzy recall* ("have we seen this before?"),
not *structured metrics* (recurrence rate, MTTR trend, worst-offender DAGs). Those need a small
structured log alongside — noted as a Phase 3 extension, not built here.

---

## Current state → target state

| | Today ([`incident_demo.py`](../mcp_slack/demo/incident_demo.py)) | After this plan |
|---|---|---|
| MCP servers connected | Slack only (one stdio session) | Slack + **RAG** + **Jira** (three sessions, merged tool list) |
| Jira ticket | Simulated (hard-coded `NOVA-4127` link) | Real `create_jira_ticket` → real key |
| Prior context | None — diagnoses cold every run | `search` incident memory *before* diagnosis |
| After resolution | Nothing recorded | `ingest` a structured incident record, keyed by ticket |
| Ticket close | Not tracked | Re-`ingest` record on close with resolution + time-to-close |

The refactor is the same pattern the demo already uses, repeated N times — see Architecture.

---

## Architecture — the multi-server connector

Today the driver opens one stdio session and hands its tools to the runner
([`incident_demo.py:98-112`](../mcp_slack/demo/incident_demo.py)):

```python
async with stdio_client(server_params()) as (read, write):
    async with ClientSession(read, write) as mcp:
        await mcp.initialize()
        tools = (await mcp.list_tools()).tools
        runner = client.beta.messages.tool_runner(
            ..., tools=[async_mcp_tool(t, mcp) for t in tools],
        )
```

`tool_runner` takes a single **flat** tool list, and each tool is already bound to *its own*
session via `async_mcp_tool(t, session)`. So multiplexing is purely additive: open three sessions,
map each server's tools to that server's session, concatenate.

```python
SERVERS = {
    "slack": StdioServerParameters(command="uv", args=["run","--project",SLACK_DIR,"slack-mcp"], ...),
    "rag":   StdioServerParameters(command="uv", args=["run","--project",RAG_DIR,"rag-mcp"], ...),
    "jira":  StdioServerParameters(command="uv", args=["run","--project",JIRA_DIR,"jira-mcp"], ...),
}

async with AsyncExitStack() as stack:
    all_tools = []
    for params in SERVERS.values():
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        server_tools = (await session.list_tools()).tools
        all_tools += [async_mcp_tool(t, session) for t in server_tools]
    runner = client.beta.messages.tool_runner(..., tools=all_tools)
```

Entry points already exist: `slack-mcp`, `rag-mcp`, `jira-mcp`. For the demo we launch each locally
with `uv run --project <dir>` (matching the current Slack launch) rather than the `uvx --from git+…`
form in each server's `mcp.yaml`, so local edits are picked up.

**Naming collision to watch:** three servers each expose their own tool names; today they don't
overlap (`ingest`/`search`/… vs `create_jira_ticket`/… vs Slack's). If a future server reuses a
name, the flat list needs a prefix. Not a problem today — just call it out.

---

## The incident record

A single free-text document per incident, ingested via `ingest(text=…, title=…, tags=…)`. The key
mechanic that makes lifecycle updates work: **a `text=` ingest is keyed in the ledger by
`text:{title}`** ([`index.py:49`](./src/rag_mcp/index.py)), and **re-ingesting the same key replaces
the prior copy** ([`index.py:67-68`](./src/rag_mcp/index.py)). So:

- **`title` = the Jira ticket key** (e.g. `NOVA-4127`) → a stable, human-meaningful ledger key.
- **Re-ingest with the same title updates the record in place** — used for the close step.
- **Ordering:** create the Jira ticket *first* (to get the real key), *then* ingest the record.

**Body** (structured markdown, so retrieval returns readable passages):

```
# Incident NOVA-4127 — novamart_inventory_sync / load_inventory
- Status: OPEN
- Detected: 2026-07-01 14:03 UTC
- Symptom: JSON schema validation error on inventory.json
- Root cause: upstream added a non-nullable column; loader schema out of date
- Fix / action: <what the ticket asks for>
- Ticket: NOVA-4127
```

**Tags** (used by `search(tags=…)`, which is any-of match):
`["incident", "<dag_name>", "<status>"]` — e.g. `["incident", "novamart_inventory_sync", "open"]`.
Tags let the pre-diagnosis search scope to incidents for *this DAG*, and let a dashboard query pull
all open vs. closed. Re-ingest replaces tags too, so `open` → `closed` on the update.

**Isolation:** point the incident-memory server at its **own `RAG_DATA_DIR`** (e.g. `.rag-incidents`)
so it never collides with a `rag-research` corpus running in the same project.

---

## New agent flow

Insert two steps into the existing system prompt
([`incident_demo.py:39-62`](../mcp_slack/demo/incident_demo.py)), around the current diagnosis and
ticket steps:

- **Before step 5 (diagnostics):** *"Search incident memory for prior occurrences of this failure:
  `search("<dag> <symptom>", tags=["incident","<dag>"])`. If a similar past incident exists, cite it
  in the thread (‘we've seen this before — NOVA-xxxx, root cause was …’) and factor it into your
  diagnosis."*
- **After step 6/7 (ticket created + root cause posted):** *"Record this incident in memory:
  `ingest(text=<structured record>, title=<real ticket key>, tags=["incident","<dag>","open"])`."*

The recurrence citation in the Slack thread is the visible demo moment — even seeded with one or two
pre-ingested past incidents, the agent will pull them up and say so live.

---

## The "track when closed" problem

This is the one genuinely non-trivial piece, because of two facts about the current tools:

1. **The Jira MCP has no transition/close write tool** — only `create`, `search`, `review`,
   `add_comment`, `list_projects` ([`jira_mcp.py`](../mcp_jira/src/jira_mcp/jira_mcp.py)). A human
   closes the ticket in Jira; the agent can **read** status back (`search_jira_tickets` and
   `review_jira_ticket` both return `status`) but cannot perform the close.
2. **The demo is a one-shot script** — there's no event loop or webhook where a close would be
   noticed.

Three implementation options, in increasing fidelity:

- **A — Demo (recommended for the showcase).** A second scripted phase / manual re-run: read the
  ticket's status via `review_jira_ticket(key)`, and if resolved, re-`ingest` the record with the
  same `title`, tags flipped to `closed`, and resolution + time-to-close appended. Demonstrates the
  full lifecycle without standing up infrastructure.
- **B — Poller.** A small loop that periodically `search`es Jira for tickets tagged as open incidents
  and re-ingests any that have transitioned. Still no new MCP capability needed; just a scheduler
  around the read tools.
- **C — Event-driven (production).** A Jira webhook → handler that re-ingests on the
  `issue_updated`/`issue_resolved` event. The real answer at fleet scale; out of scope for the demo.

Ship A now; note B/C as the production path.

---

## Build phases

- **Phase 1 — Wire it up (demo MVP).** Multi-server connector (Slack + RAG + Jira); real
  `create_jira_ticket`; pre-diagnosis `search`; post-resolution `ingest`. Seed the incident memory
  with 1–2 prior incidents so recurrence is visible on the first run.
- **Phase 2 — Lifecycle.** The close step (Option A): read status, re-ingest with resolution +
  time-to-close, flip `open`→`closed` tag. Optionally the poller (Option B).
- **Phase 3 — Metrics layer.** A thin structured log (append-only JSON/SQLite) written alongside each
  ingest, to answer the questions RAG can't: recurrence counts, MTTR trend, worst-offender DAGs.
  This is what turns the incident memory from *recall* into *reporting*.

---

## Key design decisions

- **Ticket key as the ledger key.** Using the Jira key as `title` gives a stable, meaningful
  identity and makes "update on close" a plain re-ingest — no new state, no dedupe logic.
- **Separate `RAG_DATA_DIR`.** Incident memory is its own corpus, isolated from any document RAG.
- **The agent reads status; humans (or webhooks) drive closes.** Matches how the Jira MCP is built
  today and keeps the agent honest about what it can and can't do.
- **RAG for recall, a structured log for metrics.** Don't force the vector store to do counting;
  pair it. Keeps each tool doing what it's good at.
- **No changes to the RAG or Jira servers required for Phases 1–2.** All deltas are in the demo
  driver + its system prompt. (A dedicated Jira `transition_ticket` tool would be a clean future
  addition but isn't needed here.)

---

## Open questions / dependencies

- **LLM provider.** The demo driver is Anthropic-specific (`AsyncAnthropic`, `claude-opus-4-8`,
  `beta.messages.tool_runner`) and needs `ANTHROPIC_API_KEY`. This inherits the open QBiz
  LLM-provider question — see `llm_provider_open_question` memory. The three MCP servers are
  model-agnostic; only the host driver is coupled.
- **Jira credentials.** `JIRA_URL / JIRA_EMAIL / JIRA_API_TOKEN / JIRA_DEFAULT_PROJECT` must be set
  for the real create step; without them, keep the simulated link path as a fallback.
- **Seed data.** Decide the 1–2 seed incidents so the recurrence demo has something to find.

---

## Out of scope (deliberately)

- Performing ticket transitions/closes from the agent (no Jira write tool for it today; humans close).
- A production webhook/scheduler for close tracking (Option C) — demo uses Option A.
- Structured metrics/reporting (Phase 3) — recall works without it; it's the reporting upgrade.
- Any change to the base RAG engine — this is an application of it, not a modification.

---

## Repository context

Code changes land in [`mcp/mcp_slack/demo/incident_demo.py`](../mcp_slack/demo/incident_demo.py)
(the driver) and its system prompt; they consume the existing
[RAG](./RAG_PLAN.md) and [Jira](../mcp_jira/) MCP servers unchanged. This plan sits in `mcp/mcp_rag/`
beside `RAG_PLAN.md` because the design is RAG-shaped, but it is an integration plan spanning three
servers, not a change to the RAG server itself.
