# Setup: airflow-pipeline-doctor

## Prerequisites

- `uvx` must be installed and accessible. It comes bundled with `uv`:
  ```bash
  pip install uv
  # or
  pipx install uv
  ```
  Verify with: `uvx --version`

- Your Airflow instance must be running and accessible.

## Adding the MCP to your project

```bash
qba agent mcp add astro-airflow
```

This will:
1. Prompt you for `AIRFLOW_URL`, `AIRFLOW_USERNAME`, and `AIRFLOW_PASSWORD`
2. Auto-detect your `uvx` path
3. Write the config to `.mcp.json` in your project root

## Skipping the approval prompt (optional)

By default, Claude Code will ask you to approve the MCP server once per session.
To skip this, add the following to your project's `.claude/settings.json`:

```json
{ "enableAllProjectMcpServers": true }
```

This only affects Claude Code sessions opened in this project folder.

## Local Astro dev environment

If you're running Airflow locally via the Astro CLI:
```bash
astro dev start
```
Default values: URL `http://localhost:8080`, username `admin`, password `admin`.

## Restart required

After running `qba agent mcp add`, restart your Claude Code session for the MCP to connect.
