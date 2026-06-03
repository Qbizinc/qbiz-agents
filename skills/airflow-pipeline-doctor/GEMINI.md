---
model: gemini
---

# Gemini-specific notes for airflow-pipeline-doctor

- The MCP tools are available via the connected `astro-airflow-mcp` server.
- Call `get_system_health` first, then `list_dag_runs` with state=failed.
- Use `diagnose_dag_run` to get the exact failed task_id before calling `get_task_logs`.
- Keep log summaries under 200 words — focus on the exception type and the last traceback frame.
