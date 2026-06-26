# Setup: jira-ticket-management

## Prerequisites

- **`qba` CLI installed** — Access to the Qbiz programmatic `qba` CLI utility.
- A Jira Cloud instance with a user account that has Browse Projects, Create Issues, and Add Comments permissions.
- A Jira API token — create one at https://id.atlassian.com/manage-profile/security/api-tokens

## Adding the MCP to your project

```bash
qba agent mcp add jira
```

This will prompt you for:

1. **JIRA_URL** — your Jira instance URL (e.g. `https://your-org.atlassian.net`)
2. **JIRA_EMAIL** — the email address of the service account
3. **JIRA_API_TOKEN** — the API token generated above
4. **JIRA_DEFAULT_PROJECT** — optional default project key (e.g. `PROJ`)

The CLI writes these into your project's `.mcp.json`.

## Install the skill

```bash
qba agent skills add jira-ticket-management
```

## Restart Required

Close and reopen Claude Code from your project folder so it picks up the new MCP configuration.
