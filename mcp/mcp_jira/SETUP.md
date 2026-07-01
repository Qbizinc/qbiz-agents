# Jira MCP — Setup Guide

## Prerequisites

* A Jira Cloud instance (e.g. https://your-company.atlassian.net)
* A Jira user account with permission to create and view issues
* `uv` installed locally (`pip install uv` or via https://docs.astral.sh/uv)

---

## Step 1 — Create a Jira API Token

Jira MCP uses a **service account + API token** for authentication.

1. Go to: https://id.atlassian.com/manage-profile/security/api-tokens
2. Click **Create API token**
3. Give it a name (e.g. `qbiz-agent`)
4. Copy the generated token

You will use:

* Your Jira **email address**
* The **API token** (instead of your password)

---

## Step 2 — Get Your Jira Instance URL

Your Jira URL is typically:

```
https://<your-org>.atlassian.net
```

Example:

```
https://acme.atlassian.net
```

This will be your `JIRA_URL`.

---

## Step 3 — Identify Your Project Key

Each Jira project has a short key:

* Example: `PROJ`, `DATA`, `ENG`
* You can find it in:

  * The Jira UI (issue keys like `PROJ-123`)
  * Or via the MCP `list_projects` tool after setup

Set a default project to simplify agent usage.

---

## Step 4 — Configure Environment Variables

Copy and fill in:

```bash
# Required
JIRA_URL=https://your-org.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your_api_token_here

# Optional default
JIRA_DEFAULT_PROJECT=PROJ
```

When using `qba agent mcp add jira`, the CLI can prompt for these values
and store them directly in `.mcp.json`.

---

## Step 5 — Install via qba CLI

```bash
qba agent mcp add jira
```

This will:

* Fetch the MCP server definition
* Prompt for credentials
* Write configuration into `.mcp.json`

---

## Available Tools

| Tool                  | Purpose                            |
| --------------------- | ---------------------------------- |
| `create_jira_ticket`  | Create new tasks, bugs, or stories |
| `search_jira_tickets` | Query issues using JQL             |
| `review_jira_ticket`  | Get detailed issue information     |
| `add_jira_comment`    | Add comments to issues             |
| `list_projects`       | List accessible Jira projects      |

---

## Standalone Usage (without qba)

### Option 1 — Local Project Path

```json
{
  "mcpServers": {
    "jira": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/path/to/qbiz-agents/mcp/mcp_jira",
        "jira-mcp"
      ],
      "env": {
        "JIRA_URL": "https://your-org.atlassian.net",
        "JIRA_EMAIL": "your-email@company.com",
        "JIRA_API_TOKEN": "your_api_token",
        "JIRA_DEFAULT_PROJECT": "PROJ"
      }
    }
  }
}
```

---

### Option 2 — Install via uvx (Recommended)

```bash
uvx --from git+https://github.com/Qbizinc/qbiz-agents.git#subdirectory=mcp/mcp_jira jira-mcp
```

With SSH:

```bash
uvx --from git+ssh://git@github.com/Qbizinc/qbiz-agents.git#subdirectory=mcp/mcp_jira jira-mcp
```

---

## Notes & Best Practices

* Use a **dedicated service account** for traceability (recommended)
* Keep `JIRA_DEFAULT_PROJECT` set to avoid ambiguity in agent workflows
* Use **JQL filters** in `search_jira_tickets` for precise queries
* Validate project keys using `list_projects` if unsure

---

## Troubleshooting

**Authentication errors**

* Verify email + API token (not password)
* Ensure token is active

**Project not found**

* Check project key spelling
* Use `list_projects` to confirm доступ

**Permission issues**

* Ensure the account has:

  * Browse Projects
  * Create Issues
  * Add Comments

---

This setup enables agents to fully interact with Jira for task tracking,
incident management, and workflow automation.
