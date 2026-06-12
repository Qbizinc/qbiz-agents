# Slack MCP — Live Demo

Two drivers run the same **Agentic Incident DAG** flow end-to-end through the
Slack MCP server, building an incident thread live in `#qbiz_slackbot_testing`.
Pick based on whether an LLM key is available:

| Driver | Needs | When to use |
|---|---|---|
| `incident_demo_scripted.py` | **No LLM key** | Default. A deterministic script drives the real MCP tools in the incident order. The HITL approval gate is fully live. |
| `incident_demo.py` | `ANTHROPIC_API_KEY` | Shows true agency — a real Claude (Opus 4.8) agent decides every tool call. Use once an Anthropic key is available. |

Both produce the same Slack thread; the only difference is whether a human or a
model chose the sequence. Every tool call is real either way.

## What the audience sees

A NovaMart pipeline "fails" → the incident is announced, the data owner is found,
tagged, and DMed, diagnostic findings drip into the thread, then it **pauses at a
HITL approval gate** ("Create the Jira ticket? ✅/❌"). On a human ✅ it posts the
root cause, uploads a playbook, and ✅-reacts the root message as resolved. On ❌
(or timeout) it holds off and stops — the safety behavior.

## Run it

```bash
# from mcp/mcp_slack/

# No-LLM scripted driver (recommended while the LLM provider is undecided):
uv run python demo/incident_demo_scripted.py

# LLM-driven driver (needs ANTHROPIC_API_KEY):
uv run --with "anthropic[mcp]" python demo/incident_demo.py
```

The scripted driver takes optional env knobs: `DEMO_CHANNEL`, `DEMO_OWNER`,
`APPROVAL_TIMEOUT` (default 90s), `STEP_DELAY` (default 1.5s).

## Prerequisites

| # | Requirement | Notes |
|---|---|---|
| 1 | `.env` with `SLACK_BOT_TOKEN` / `SLACK_APP_TOKEN` / `SLACK_SIGNING_SECRET` | Already present locally; the server loads it. |
| 2 | `@qbizslackbot` invited to `#qbiz_slackbot_testing` | `/invite @qbizslackbot` (done). |
| 3 | `reaction_added` bot event subscribed | Done — the HITL gate resolves on a live reaction. If it were missing, `request_approval` would just time out and the flow would halt at the gate. |
| 4 | `ANTHROPIC_API_KEY` | **Only** for `incident_demo.py`. The scripted driver needs no key. |

## Presenter tips

- Have `#qbiz_slackbot_testing` open on the projector — Slack *is* the UI.
- When the approval prompt appears, react ✅ live so the audience sees the flow
  resume on a human signal. React ❌ to show the halt path.
- The scripted driver is the safe choice for a live demo — deterministic timing,
  no key, no model variance. Verified end-to-end (all 9 steps, live approval).
