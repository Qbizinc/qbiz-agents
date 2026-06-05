# Slack MCP — Setup Guide

## Prerequisites

- A Slack workspace where you have permission to install apps
- `uv` installed locally (`pip install uv` or via [docs.astral.sh/uv](https://docs.astral.sh/uv))

---

## Step 1 — Create the Slack App

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. Give it a name (e.g. `qbiz-agent-bot`) and select your target workspace
3. Under **OAuth & Permissions → Scopes → Bot Token Scopes**, add the following:

| Scope | Purpose |
|---|---|
| `chat:write` | Post messages to channels and DMs |
| `chat:write.public` | Post to channels the bot hasn't joined |
| `files:write` | Upload files |
| `files:read` | Read file metadata |
| `channels:read` | List public channels |
| `groups:read` | List private channels the bot is in |
| `im:write` | Open DM conversations |
| `im:read` | Read DM channel IDs |
| `users:read` | Look up users by name |
| `users:read.email` | Look up users by email address |
| `channels:history` | Read channel message history |
| `im:history` | Read DM history |
| `reactions:write` | Add emoji reactions |
| `reactions:read` | Read reactions (required for HITL approval detection) |

4. Click **Install App to Workspace** → copy the **Bot User OAuth Token** (`xoxb-...`)
5. From **Basic Information**, copy the **Signing Secret**

---

## Step 2 — Enable Socket Mode (recommended)

Socket Mode lets the bot receive events without a public URL. It is required for the
`wait_for_reply` and `request_approval` tools (Phase 10b / HITL checkpoints).

1. Under **Socket Mode**, toggle it on
2. Generate an **App-Level Token** (`xapp-...`) with the `connections:write` scope
3. Copy the token — this is your `SLACK_APP_TOKEN`

If you only need one-way posting (sending messages, uploading files), Socket Mode and
`SLACK_APP_TOKEN` are optional.

---

## Step 3 — Subscribe to Events (for two-way communication)

Under **Event Subscriptions → Subscribe to Bot Events**, add:

- `message.channels` — messages in public channels the bot is in
- `message.im` — direct messages to the bot
- `app_mention` — @mentions of the bot
- `reaction_added` — emoji reactions (needed for approval detection)

---

## Step 4 — Configure Environment Variables

Copy the template and fill in your credentials:

```bash
# Required
SLACK_BOT_TOKEN=xoxb-...           # Bot OAuth token (OAuth & Permissions page)
SLACK_SIGNING_SECRET=...           # Signing secret (Basic Information page)

# Required for Socket Mode / two-way communication
SLACK_APP_TOKEN=xapp-...           # App-level token with connections:write scope

# Optional defaults
SLACK_DEFAULT_CHANNEL=#general         # Fallback channel when none is specified
SLACK_INCIDENT_CHANNEL=#data-incidents # Channel for incident thread announcements
```

When using `qba agent mcp add slack`, the CLI will prompt for each of these values
and write them directly into `.mcp.json` — no `.env` file needed for that flow.

---

## Step 5 — Install via qba CLI

```bash
qba agent mcp add slack
```

This fetches the MCP definition from the qbiz-agents registry, prompts for credentials,
and writes the server config to `.mcp.json` in your project root.

---

## Standalone Usage (without qba)

Add this block to your `.mcp.json` manually, pointing at your local qbiz-agents clone:

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

Or install directly from the repo via uvx:

```bash
uvx --from git+ssh://git@github.com/Qbizinc/qbiz-agents.git#subdirectory=mcp/mcp_slack slack-mcp
```
