# Slack MCP — Live Demo

`incident_demo.py` runs a real Claude agent (Opus 4.8) that drives the **Agentic
Incident DAG** flow end-to-end through the Slack MCP server. The LLM decides every
tool call; you just trigger it and watch the thread build itself in
`#qbiz_slackbot_testing`.

## What the audience sees

A NovaMart pipeline "fails" → the agent announces the incident, finds the data
owner, tags + DMs them, posts diagnostic findings into the thread, **pauses at a
HITL approval gate** ("Create the Jira ticket? ✅/❌"), then on approval posts the
root cause, uploads a playbook, and ✅-reacts the root message as resolved.

## Run it

```bash
# from mcp/mcp_slack/
uv run --with "anthropic[mcp]" python demo/incident_demo.py
```

## Prerequisites

| # | Requirement | Notes |
|---|---|---|
| 1 | `ANTHROPIC_API_KEY` in the environment | The agent's brain. |
| 2 | `.env` with `SLACK_BOT_TOKEN` / `SLACK_APP_TOKEN` / `SLACK_SIGNING_SECRET` | Already present locally; the server loads it. |
| 3 | `@qbizslackbot` invited to `#qbiz_slackbot_testing` | `/invite @qbizslackbot` (done). |
| 4 | **`reaction_added` bot event subscribed** | Required for the HITL gate to resolve. Without it, `request_approval` times out after 90s and the agent proceeds, noting the timeout — the rest of the flow still demos cleanly. See repo `SLACK_MCP_PLAN.md` Phase 1.2 / Event Subscriptions. |

## Presenter tips

- Have `#qbiz_slackbot_testing` open on the projector — Slack *is* the UI.
- When the approval prompt appears, react ✅ live so the audience sees the agent
  resume on a human signal. (Requires prerequisite #4.)
- To show the rejection path, react ❌ instead — the agent holds off and stops.
