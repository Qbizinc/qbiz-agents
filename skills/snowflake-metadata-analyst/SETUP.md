# Setup: snowflake-metadata-analyst

## Prerequisites

- Access to the Qbiz programmatic `qba` CLI utility.
- Valid, active programmatic credentials (PAT or OAuth token) matching an account role with `SELECT` and `USAGE` privileges inside your target Snowflake environment.

## Adding the MCP to your project

Execute the following installation command in your local project root directory:

```bash
qba agent mcp add snowflake-managed
```

This will automatically guide you through configuring your project connection parameters:  

  URL: Supply your explicit enterprise streamable endpoint pointing to your target database, schema, and MCP server cluster.

  Token: Supply your bearer authentication payload token.  

The CLI will append these values directly into your local workspace .mcp.json file.

## Restart Required

Once the .mcp.json structure is fully updated, close and restart your active agent or Claude Code session to let the streamable-http pipeline initialize.
