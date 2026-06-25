# Setup: snowflake-data-explorer

## Prerequisites

-  **`qba` CLI installed** - Access to the Qbiz programmatic `qba` CLI utility.
- Valid, active programmatic credentials (PAT or OAuth token) matching an account role with `SELECT` and `USAGE` privileges inside your target Snowflake environment.

## Adding the MCP to your project

Execute the following installation command in your local project root directory:

```bash
qba agent mcp add snowflake
```

This will automatically guide you through configuring your project connection parameters:  

1. URL: Supply your explicit enterprise streamable endpoint pointing to your target database, schema, and MCP server cluster.
2. Token: Supply your bearer authentication payload token.  

The CLI will append these values directly into your local workspace .mcp.json file.

## Update Skills 

```bash 
qba agent skills add snowflake-data-explorer
```

## Skipping the approval prompt (optional)

By default, Claude Code will ask you to approve the MCP server once per session.
To skip this, add the following to your project's `.claude/settings.json`:

```json
{ "enableAllProjectMcpServers": true }
```

This only affects Claude Code sessions opened in this project folder.

## Restart Required

Once the .mcp.json structure is fully updated, close and restart your active agent or Claude Code session to let the streamable-http pipeline initialize.
