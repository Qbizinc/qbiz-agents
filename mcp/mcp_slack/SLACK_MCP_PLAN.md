# Slack MCP Server — Implementation Plan

## Overview

A reusable Model Context Protocol (MCP) server that exposes Slack integration as tools consumable
by any MCP-compatible LLM client (Claude Desktop, Claude Code, custom agents, etc.).

**Design goals:**
- Fully self-contained Python package — drop into any project via config, not code
- All credentials injected via environment variables; no hardcoded workspace info
- Supports one-way posting (text + files) and two-way interactive communication
- Works in both local-dev (Socket Mode) and production (HTTP + Events API) modes

---

## Project Context

### Immediate use case — Agentic Incident DAG (Qbiz · Airflow Summit 2026)

This MCP is one component of a conference demo where an AI agent auto-investigates Airflow
pipeline failures. When a NovaMart pipeline breaks, the Agentic Incident DAG fires, runs
diagnostics against Airflow/AWS/Redshift MCP servers, then uses this Slack MCP to communicate
findings in real time.

**Expected incident flow (tool call sequence):**
1. `send_message` → posts incident announcement to `#data-incidents`; capture returned `ts` as the thread root
2. `find_user` → resolves data owner name **and Slack user ID** for the failing pipeline
3. `send_message` (with `thread_ts`) → tags data owner (`<@USER_ID>`) in the thread so team visibility is immediate; this is distinct from the DM — it puts their name on the public record
4. `send_dm` → notifies data owner privately with a direct link to the investigation thread
5. `send_message` (with `thread_ts`) → appends diagnostic findings as investigation proceeds (called multiple times)
6. `send_message` (with `thread_ts`) → posts final root cause summary; **must include the Jira ticket link** supplied by the Jira MCP (see Inputs below)
7. `upload_file` → attaches the final versioned playbook to the thread
8. `add_reaction` (`:white_check_mark:`) → signals investigation complete on the root message

This is primarily a **one-way posting** flow during the demo. The agent does not wait for human
replies mid-investigation — the LLM drives the entire sequence autonomously.

**Repository context:** This server lives in [`qbiz-agents`](https://github.com/Qbizinc/qbiz-agents)
at `mcp/mcp_slack/`, alongside the Airflow MCP and any future Qbiz or vendor MCPs. It is
registered in the `qba` CLI registry so consultants can install it via `qba agent mcp add slack`.
The package is self-contained and can also be used standalone via `uvx --from git+ssh://...` or
a local `uv run --project` reference without pulling in the rest of the repo. See
[Integration History](#integration-history) for the full migration notes.

### Harness Architecture Context (Qbiz methodology)

Per Qbiz's enterprise AI agent positioning, **Slack is not just a notification channel — it is the
primary HITL (Human-in-the-Loop) checkpoint mechanism.** The harness pattern is:

> _"Python pauses execution and fires a notification (Slack, email, webhook). Waits for approval
> signal before continuing."_ — Slide 33, Harness Component Build Reference

This means this MCP needs to support two distinct patterns:

**Pattern A — One-way reporting** (incident thread posting, already planned)
The agent posts findings and files to a channel thread. No reply expected.

**Pattern B — HITL approval gate** (needed for consequential actions)
The agent posts a decision prompt to Slack, waits for an engineer to react with ✅ or ❌,
then proceeds or halts based on that signal. Example in the demo: before creating a Jira ticket
or marking a pipeline for restart, the agent posts: _"Root cause identified: schema mismatch on
`inventory.json`. Create Jira incident? ✅ Yes / ❌ Cancel."_

The HITL moment is **the most compelling thing to show in the demo** — it transforms the agent
from a read-only investigator into a system that takes action with human sign-off.

**Implication for this MCP:** Two-way communication (`wait_for_reply` / reaction listening) is
**not** a stretch goal. It is required to fulfill the Qbiz harness pattern and to make the demo
genuinely impressive. It moves up to Phase 10a. See Phase 6 for implementation details.

**Security note (Slide 40):** Incoming Slack messages are explicitly called out by Qbiz as a
prompt injection vector — _"crafting prompt injection attempts via the channels the agent reads."_
Content returned by `wait_for_reply` and `get_channel_history` must be treated as potentially
hostile data by the harness input wrapper. This MCP returns raw content; sanitization belongs
in the calling agent's harness layer, not here.

---

### Secondary use case — Template

This codebase belongs to Qbiz. 
However, this project serves as a complete reference implementation. Once finished, the same
design decisions, Slack App configuration steps, tool definitions, and project structure can be
replicated from scratch to build equivalents, say for Clients who want to own the code — without starting from zero.
The PLAN.md itself (this file) is the primary artifact that carries those learnings across.

See Phase 9 for the reusability checklist written with that replication in mind.

---

## Phase 1 — Slack App Setup

### 1.1 Create the Slack App

1. Go to https://api.slack.com/apps → **Create New App** → **From scratch**
2. Give it a name (e.g. `mcp-slack-bot`) and select your target workspace
3. Under **OAuth & Permissions → Scopes → Bot Token Scopes**, add:

   | Scope | Purpose |
   |---|---|
   | `chat:write` | Post messages to channels/DMs |
   | `chat:write.public` | Post to channels the bot hasn't joined |
   | `files:write` | Upload files |
   | `files:read` | Read file metadata |
   | `channels:read` | List public channels |
   | `groups:read` | List private channels the bot is in |
   | `im:write` | Open DMs |
   | `im:read` | Read DM channel IDs |
   | `users:read` | Look up users by name/email |
   | `channels:history` | Read channel message history |
   | `im:history` | Read DM history |
   | `reactions:write` | Add emoji reactions (for acknowledgement UX) |
   | `reactions:read` | Read reactions on messages (required for HITL approval detection) |

4. **Install App to Workspace** → copy the **Bot User OAuth Token** (`xoxb-...`)
5. Copy the **Signing Secret** from **Basic Information**

### 1.2 Choose Communication Mode

**Socket Mode** (recommended for local dev and most deployments):
- No public URL needed; Slack connects outbound via WebSocket
- Enable under **Socket Mode** → generate an **App-Level Token** (`xapp-...`) with scope `connections:write`

**HTTP Events API** (for production servers with a public URL):
- Enable under **Event Subscriptions** → provide a public endpoint URL
- Requires verifying the Slack signature on incoming requests

For two-way communication and HITL approval detection, subscribe to these **Bot Events**:
- `message.channels` — messages posted in public channels the bot is in
- `message.im` — direct messages sent to the bot
- `app_mention` — when someone @mentions the bot
- `reaction_added` — when a user adds an emoji reaction (needed for `request_approval`)

---

## Phase 2 — Project Structure

The package now lives inside `qbiz-agents`. The layout below reflects its current location:

```
qbiz-agents/
└── mcp/
    └── mcp_slack/
        ├── mcp.yaml            # qba registry definition (command, env vars, tools list)
        ├── pyproject.toml      # Package metadata + dependencies (name: qbiz-slack-mcp)
        ├── SETUP.md            # Slack app creation guide and credential setup
        ├── SLACK_MCP_PLAN.md   # This file
        └── src/
            └── slack_mcp/
                ├── __init__.py
                ├── _app.py         # FastMCP singleton
                ├── server.py       # Entry point + tool registration
                ├── slack_client.py # Thin wrapper around slack_sdk
                ├── listener.py     # Socket Mode event listener (Phase 10b)
                └── tools/
                    ├── __init__.py
                    ├── messaging.py    # send_message, send_dm, add_reaction
                    ├── files.py        # upload_file
                    ├── channels.py     # list_channels, get_channel_history
                    └── users.py        # find_user
```

---

## Phase 3 — Dependencies

**pyproject.toml** (use `uv` or `pip`):

```toml
[project]
name = "qbiz-slack-mcp"         # Renamed from slack-mcp to avoid PyPI collisions
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.0.0",               # Anthropic MCP SDK
    "slack-sdk>=3.27.0",        # Slack official Python SDK
    "python-dotenv>=1.0.0",     # .env loading
    "aiohttp>=3.9.0",           # Async HTTP (required for Socket Mode client)
]

[project.scripts]
slack-mcp = "slack_mcp.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

---

## Phase 4 — Environment Variables

```dotenv
# .env.example

# Required
SLACK_BOT_TOKEN=xoxb-...          # Bot OAuth token
SLACK_SIGNING_SECRET=...          # For HTTP mode signature verification

# Required only for Socket Mode (recommended)
SLACK_APP_TOKEN=xapp-...          # App-level token with connections:write scope

# Optional
SLACK_DEFAULT_CHANNEL=#general        # Fallback channel if none specified
SLACK_INCIDENT_CHANNEL=#data-incidents # Channel for incident thread announcements (Qbiz demo)
SLACK_MODE=socket                     # "socket" (default) or "http"
SLACK_HTTP_PORT=3000                  # Only used in HTTP mode
```

---

## Phase 5 — MCP Server & Tool Definitions

### 5.1 Server entry point (`server.py`)

```python
from mcp.server import Server
from mcp.server.stdio import stdio_server
from dotenv import load_dotenv

load_dotenv()

server = Server("slack-mcp")

# Register all tools (see Phase 5.2)
from slack_mcp.tools import messaging, files, channels, users  # noqa: F401

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
```

### 5.2 Tools to implement

#### `send_message`
- **Inputs:** `channel` (name or ID), `text`, `thread_ts` (optional, for threading), `jira_url` (optional, appended as a labeled link in the final summary message)
- **Behavior:** Resolves channel name → ID if needed; falls back to `SLACK_DEFAULT_CHANNEL`; when `jira_url` is provided, appends `:jira: *Incident ticket:* <URL|View in Jira>` to the message text
- **Returns:** Message timestamp (`ts`) for follow-up threading
- **Note on tagging:** To @mention a data owner in the thread, include `<@USER_ID>` in the `text` field (ID returned by `find_user`). This is required for the initial thread tag (step 3 of the incident flow) — plain display names are not clickable and do not trigger Slack notifications

#### `send_dm`
- **Inputs:** `user` (display name, real name, or email), `text`
- **Behavior:** Resolves user → opens IM channel → posts message
- **Returns:** Message timestamp

#### `upload_file`
- **Inputs:** `channel`, `filename`, `content` (base64 or text), `content_type`, `title` (optional), `initial_comment` (optional)
- **Behavior:** Uses `files_upload_v2` API; supports text and binary content
- **Returns:** File permalink

#### `list_channels`
- **Inputs:** `include_private` (bool, default false), `limit` (default 100)
- **Returns:** Array of `{id, name, is_private, member_count}`

#### `get_channel_history`
- **Inputs:** `channel`, `limit` (default 20), `oldest` (optional Unix timestamp)
- **Returns:** Array of `{ts, user, text, thread_ts}` messages

#### `find_user`
- **Inputs:** `query` (name, display name, or email)
- **Returns:** Array of `{id, name, real_name, email}` matches

#### `add_reaction`
- **Inputs:** `channel`, `timestamp`, `emoji` (e.g. `"thumbsup"`)
- **Behavior:** Adds an emoji reaction to a specific message
- **Use case:** Acknowledgement signals; also used by `request_approval` to confirm receipt

#### `request_approval`
- **Inputs:** `channel`, `prompt` (question text), `timeout_seconds` (default 120), `thread_ts` (optional)
- **Behavior:**
  1. Posts `prompt` to `channel` with instructions: _"React ✅ to approve or ❌ to cancel"_
  2. Listens for a `reaction_added` event on that specific message (keyed by `channel` + `ts`)
  3. Resolves when ✅ or ❌ reaction is received, or when timeout elapses
- **Returns:** `{decision: "approved" | "rejected" | "timed_out", user: str, ts: str}`
- **Use case:** HITL checkpoint — pauses agent execution until an engineer approves a consequential
  action (creating a Jira ticket, restarting a pipeline, etc.)
- **Note:** Requires Socket Mode listener to be running (`SLACK_APP_TOKEN` must be set)

### 5.3 Message Structure Templates

The acceptance criterion requires messages to be "readable and structured for a technical data owner." These templates define the plain-text structure each message type must follow. Block Kit is a post-demo upgrade; these text patterns satisfy the AC now.

**Incident announcement (step 1 — root thread message):**
```
:rotating_light: *Incident Detected*
*Pipeline:* <pipeline_name>
*Error:* <error_type>
*Time:* <timestamp UTC>

Investigation starting. Updates will follow in this thread.
```

**Data owner tag (step 3 — threaded):**
```
<@USER_ID> You are the listed owner for *<pipeline_name>*. Tagging you for awareness.
```

**Investigation update (step 5 — threaded, repeated):**
```
:mag: *Finding — <timestamp>*
<finding_text>
```

**Final root cause summary (step 6 — threaded):**
```
:white_check_mark: *Root Cause Identified*
*Cause:* <root_cause_summary>
*Playbook:* See attached file below.
:jira: *Incident ticket:* <jira_url|View in Jira>
```

These templates are produced by the **calling agent** (the Agentic Incident DAG), not enforced by this MCP — the MCP accepts freeform `text`. However, the agent's system prompt must reference these templates so output is consistent across runs. Document the templates in the README so the DAG author (Andres) can copy them directly.

---

## Phase 6 — Two-Way Communication & HITL Checkpoints

### 6.1 Why this matters

The Qbiz harness architecture explicitly identifies Slack as the HITL approval channel:
_"Python pauses execution and fires a notification (Slack, email, webhook). Waits for approval
signal before continuing."_

The `request_approval` tool implements this pattern as a first-class MCP tool. The demo's most
compelling moment is when the agent pauses mid-investigation and asks for human sign-off before
creating a Jira ticket. This requires the Socket Mode listener to be running.

### 6.2 Implementation approach

**Socket Mode listener** (the only viable approach for real-time HITL):
- A background async task connects to Slack via WebSocket
- Dispatches incoming events into two in-memory queues:
  - `_message_queues: dict[str, Queue]` — keyed by channel ID, receives `message` / `app_mention` events
  - `_reaction_queues: dict[tuple[str, str], Queue]` — keyed by `(channel_id, message_ts)`, receives `reaction_added` events
- `wait_for_reply` pulls from `_message_queues`
- `request_approval` posts a prompt, then pulls from `_reaction_queues` for that specific message

#### `wait_for_reply` tool
- **Inputs:** `channel`, `after_ts`, `timeout_seconds` (default 60)
- **Behavior:** Blocks until a new message arrives after `after_ts`, or times out
- **Returns:** `{user, text, ts}` or `{timed_out: true}`
- **Use case:** Reading replies to agent-posted questions; async check-ins

### 6.3 Listener event routing sketch

```python
# _message_queues: keyed by channel_id
# _reaction_queues: keyed by (channel_id, message_ts)

async def handle(sc, req: SocketModeRequest) -> None:
    event = req.payload.get("event", {})
    etype = event.get("type")

    if etype in ("message", "app_mention"):
        channel = event.get("channel")
        if channel in _message_queues:
            await _message_queues[channel].put(event)

    elif etype == "reaction_added":
        channel = event.get("item", {}).get("channel")
        ts = event.get("item", {}).get("ts")
        key = (channel, ts)
        if key in _reaction_queues:
            await _reaction_queues[key].put(event)
```

---

## Phase 7 — MCP Client Configuration

### Option A — via qba CLI (recommended)

If the consuming project uses the `qba` agent CLI, run:

```bash
qba agent mcp add slack
```

The CLI fetches `mcp.yaml` from the qbiz-agents registry, prompts for credentials, and writes
the server config to `.mcp.json` automatically.

### Option B — via uvx from GitHub (no local clone needed)

Add to `.mcp.json` in the consuming project:

```json
{
  "mcpServers": {
    "slack": {
      "command": "uvx",
      "args": [
        "--from", "git+ssh://git@github.com/Qbizinc/qbiz-agents.git#subdirectory=mcp/mcp_slack",
        "slack-mcp"
      ],
      "env": {
        "SLACK_BOT_TOKEN": "xoxb-...",
        "SLACK_APP_TOKEN": "xapp-...",
        "SLACK_SIGNING_SECRET": "..."
      }
    }
  }
}
```

### Option C — via local clone (fastest iteration during development)

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

For use as a library in a larger Python project, the server can also be launched as a subprocess
or embedded via the MCP `in-process` transport.

---

## Phase 8 — Testing Plan

### Unit tests
- Mock `slack_sdk.WebClient` responses
- Test channel/user name resolution logic
- Test tool input validation (missing required fields, invalid types)

### Integration tests (needs real Slack app)
- Post a message to a test channel → verify it appears
- Upload a small text file → verify permalink returned
- Send a DM → verify delivery
- Socket Mode listener → post manually in Slack → verify `wait_for_reply` unblocks

### Test environment setup
- Create a dedicated `#mcp-test` channel in the workspace
- Use a separate Slack App for testing vs. production

---

## Phase 9 — Reusability Checklist

To use this server in a new project (day job, Varvite/Outcrop, or any future client):

- [ ] Create a new Slack App in the target workspace (Phase 1)
- [ ] Copy required OAuth scopes exactly as listed
- [ ] Provide environment variables (no code changes needed)
- [ ] Add the MCP server config block to the client's MCP config file
- [ ] If using two-way communication, ensure `SLACK_APP_TOKEN` is set and Socket Mode is enabled

The server itself requires **zero code changes** between deployments — all workspace-specific
configuration lives in environment variables.

---

## Phase 10 — Implementation Order

Priority is shaped by the Airflow Summit demo timeline (June 2026).

**Phase 10a** covers the full demo-critical path, including HITL — `request_approval` is the
single most compelling demo moment and is not optional.
**Phase 10b** covers non-critical polish and test infrastructure.

### Phase 10a — Demo-critical (build in order)

1. [x] Scaffold project with `pyproject.toml` and directory structure
2. [x] Implement `slack_client.py` wrapper (auth, channel/user resolution helpers)
3. [x] Implement `send_message` with thread support
4. [x] Implement `send_dm`, `find_user`, `add_reaction`, `upload_file`
5. [x] Implement `list_channels`, `get_channel_history`
6. [x] Wire all tools into `server.py` — verify 7 tools register cleanly ✓
7. [ ] Smoke test full incident thread sequence manually end-to-end

### Phase 10b — Post-demo (build if time permits or for future use)

8. [ ] Implement Socket Mode listener with dual-queue routing (messages + reactions)
9. [ ] Implement `wait_for_reply` tool (pulls from message queue)
10. [ ] Implement `request_approval` tool (HITL approval gate — potential demo wow factor)
11. [ ] Wire listener startup into `server.py` (start on boot when `SLACK_APP_TOKEN` is set)
12. [ ] Write unit tests with mocked Slack client
13. [ ] Write integration test suite
14. [ ] Document deployment / replication steps in README

---

## Post-Demo / Future Considerations

None of these are required for the demo. The demo is controlled, so security threat models,
multi-workspace support, and compliance concerns are out of scope. Items below are captured
for when this MCP is used in production contexts or replicated for Varvite.

- **Rate limiting:** Slack Tier 3 methods allow ~50 req/min. Add retry logic with exponential
  backoff via `slack_sdk`'s built-in `RetryHandler` for high-volume use.
- **Multi-workspace:** Currently scoped to one workspace per server instance. For multi-workspace
  support, extend env config to accept multiple token sets keyed by workspace name.
- **Slash commands:** Slack slash commands (user-initiated) can be forwarded to the LLM if a
  web endpoint is available — out of scope for v1 but a natural v2 extension.
- **Scheduled messages:** `chat.scheduleMessage` API available if needed.
- **Message formatting:** Slack Block Kit for rich messages (buttons, dropdowns) — useful for
  interactive approval flows and confirmation UX in agent pipelines (v2 priority for Varvite).
- **Qbiz demo coordination:** This MCP now lives in `qbiz-agents/mcp/mcp_slack/` — the layout
  and integration are complete. Align with Andres on how the Agentic Incident DAG references
  it (via `qba agent mcp add slack` or a direct `.mcp.json` entry).
- **Data owner mapping:** The demo needs to know which Slack user owns each NovaMart pipeline.
  Consider a `PIPELINE_OWNERS` env var (JSON map of pipeline name → Slack user email/name) so
  the agent can resolve owners without hardcoded values in the DAG.
- **Prompt injection via Slack (security):** Per Qbiz's own red team guidance, incoming Slack
  messages are a prompt injection vector. Content returned by `wait_for_reply` and
  `get_channel_history` is raw user input and must pass through the calling agent's input wrapper
  before the LLM sees it. This MCP does not sanitize — that responsibility belongs in the harness.
- **Audit logging:** Qbiz architecture requires every agent action logged to a durable,
  tamper-evident store. The calling harness is responsible for this, but the MCP should return
  enough structured metadata (channel IDs, timestamps, user IDs, file permalinks) to make every
  action reconstructible. Confirm all tool return values include these fields before demo.
- **HITL in the demo risk tier:** The Agentic Incident DAG is a write-capable agent (creates
  Jira tickets, posts to Slack) — Qbiz's own framework puts it at HIGH risk tier, requiring
  HITL checkpoints + output validation + audit trail as minimum harness. `request_approval`
  fulfills the HITL requirement for any action the agent takes beyond read-only investigation.

---

## Integration History

### 2026-06-05 — Migrated into qbiz-agents

**Decision:** `qbiz-agents` was established as the central hub for all Qbiz agent-related work —
both internally-built MCP servers (like this one) and vendor MCPs (like `astro-airflow`). This
gives consultants a single repo to go to for all agent needs, and ensures work from one project
is available to future projects without starting from scratch.

**What was done:**

- Moved all source from the standalone `Slack_MCP/` project into `qbiz-agents/mcp/mcp_slack/`
  following the `mcp_<name>/` naming convention established by `mcp_astro_airflow`
- Renamed the Python package from `slack-mcp` to `qbiz-slack-mcp` to avoid PyPI naming
  collisions and make ownership clear; the CLI entry point (`slack-mcp`) is unchanged
- Created `mcp.yaml` registering the server in the `qba` CLI — users can now run
  `qba agent mcp add slack` to install it into any project's `.mcp.json`
- Created `SETUP.md` documenting Slack app creation, required OAuth scopes, and all three
  installation methods (qba CLI, uvx from GitHub, local clone)
- Regenerated `checksums.sha256` to include the new mcp_slack files
- Branch: `feature/slack-mcp-integration`

**What did not change:** All Python source code is identical to the original `Slack_MCP/`
implementation. The original `Slack_MCP/` directory is preserved as a reference.

**Installation going forward:** New projects should use `qba agent mcp add slack`. For active
development on this MCP itself, use the local clone path (Option C in Phase 7).
