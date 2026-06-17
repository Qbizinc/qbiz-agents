# Setup: slack-bot-setup

How to stand up the Slack MCP server in a workspace — including deploying it for a
client. The QBiz `qbizslackbot` is the working reference; each new deployment is
the same server with a **new Slack app and its own tokens**.

## Mental model (read this first)

- **One Slack app per workspace.** A Slack app and its bot token are bound to a
  single workspace. You cannot reuse the QBiz bot's tokens for a client — each
  client gets their **own** Slack app, created in **their** workspace, by someone
  with permission to install apps there.
- **The server code never changes.** Everything workspace-specific is environment
  variables (`SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_SIGNING_SECRET`, optional
  channel defaults). Replication = repeat the Slack-app steps below and supply new env.
- **Prerequisite:** `uv` installed (`pip install uv`), and for the `qba` install
  flow, the `qba` CLI.

The canonical, detailed app-creation walkthrough lives at
`mcp/mcp_slack/SETUP.md`. This file is the deploy/replicate playbook and the
hard-won gotchas; follow both.

## Step 1 — Create the Slack app (in the target workspace)

api.slack.com/apps → **Create New App → From scratch** → name it (e.g.
`<client>-agent-bot`) → pick the workspace.

Under **OAuth & Permissions → Bot Token Scopes**, add:

| Scope | Why |
|---|---|
| `chat:write`, `chat:write.public` | Post to channels / DMs, incl. channels not joined |
| `files:write`, `files:read` | Upload files |
| `channels:read`, `groups:read` | List channels |
| `im:write`, `im:read` | Open / read DMs |
| `users:read`, `users:read.email` | Look up users by name / email |
| `channels:history`, `im:history` | Read history (`get_channel_history`, `wait_for_reply`) |
| `reactions:write`, `reactions:read` | Add reactions; **detect approvals (HITL)** |

Install to workspace → copy the **Bot User OAuth Token** (`xoxb-…`) and the
**Signing Secret** (Basic Information).

## Step 2 — Socket Mode (required for HITL)

Only needed for `request_approval` / `wait_for_reply`. Skip if you only post.

**Socket Mode** → enable → generate an **App-Level Token** (`xapp-…`) with
`connections:write`. That is `SLACK_APP_TOKEN`.

## Step 3 — Event subscriptions (required for HITL) ⚠️

This is the step most easily missed — without it the HITL tools silently time out.

**Event Subscriptions** → Enable Events → **Subscribe to bot events** → add
`reaction_added` (approvals), and `message.channels`, `message.im`, `app_mention`
(for `wait_for_reply`) → **Save** → **reinstall the app** when prompted (new event
scopes require a reinstall).

Verify it actually delivers: with the bot in a channel, react to one of its messages
and confirm `request_approval` resolves. (The `hitl`-marked test in
`mcp/mcp_slack/tests/` does exactly this.)

## Step 4 — Invite the bot to its channels

Run `/invite @<bot-name>` in every channel the bot will **react in or listen to**.
Membership is required for `reactions.add` and for receiving events — posting via
`chat:write.public` alone is not enough.

## Step 5 — Wire up the MCP server

**Via `qba` (recommended):**
```bash
qba agent mcp add slack
```
Prompts for the tokens and writes `.mcp.json`. Then restart the agent session.

**Manually** (`.mcp.json`), pointing at a local clone:
```json
{
  "mcpServers": {
    "slack": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/qbiz-agents/mcp/mcp_slack", "slack-mcp"],
      "env": {
        "SLACK_BOT_TOKEN": "xoxb-...",
        "SLACK_APP_TOKEN": "xapp-...",
        "SLACK_SIGNING_SECRET": "..."
      }
    }
  }
}
```
Or run straight from the repo: `uvx --from git+ssh://git@github.com/Qbizinc/qbiz-agents.git#subdirectory=mcp/mcp_slack slack-mcp`.

Optional env: `SLACK_DEFAULT_CHANNEL`, `SLACK_INCIDENT_CHANNEL`.

## Step 6 — Verify

- Post: ask the agent to send a test message to a channel the bot is in.
- HITL: trigger `request_approval`, react ✅ in Slack, confirm it returns `approved`.
- There's a runnable, no-LLM demo of the full flow at
  `mcp/mcp_slack/demo/incident_demo_scripted.py`.

## Client replication checklist

- [ ] New Slack app created **in the client's workspace** (Step 1)
- [ ] Bot token scopes added exactly as above
- [ ] Socket Mode + app token (if HITL) — Step 2
- [ ] Bot events subscribed **and app reinstalled** (if HITL) — Step 3
- [ ] Bot invited to its channels — Step 4
- [ ] `.mcp.json` populated with the **client's** tokens — Step 5
- [ ] Posting + HITL verified in the client's workspace — Step 6

Zero code changes between deployments — only the env values differ. Store each
client's tokens in that client's secrets manager; never commit them.

## Further reference

- `mcp/mcp_slack/SETUP.md` — canonical app-creation detail
- `mcp/mcp_slack/SLACK_MCP_PLAN.md` — design rationale, HITL architecture, security notes
- `mcp/mcp_slack/demo/README.md` — runnable demo (scripted + LLM-driven)
