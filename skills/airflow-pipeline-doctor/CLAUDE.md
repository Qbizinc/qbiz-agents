---
model: claude
---

# Claude-specific notes for airflow-pipeline-doctor

- Use the Skill tool to invoke this skill. The MCP tools (`get_system_health`, `list_dag_runs`, etc.) are available directly in your tool list when `astro-airflow-mcp` is connected.
- Call `get_system_health` and `list_dag_runs` in parallel on the first pass to save time.
- Use `diagnose_dag_run` before `get_task_logs` — it gives you the exact task_id and try_number needed for the logs call.
