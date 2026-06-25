# Claude-specific notes for snowflake-data-explorer

- Invoke via the Skill tool. The MCP tool (`airflow_incident_mcp`) is available directly in your tool list when `snowflake-managed` is connected — call it directly.
- **Peer Join Validation**: Before assembling complex multi-table joins, utilize your internal `<thinking>` space to inspect historical query behavior and extract validated query logic from past executions. Map out whether this is an exploration task or a diagnostic task. Write your draft SQL inside this thinking block to review for syntax errors before execution.
- Leverage parallel execution loops within a single conversational turn to retrieve schema architecture and query history logs concurrently (e.g., requesting `COLUMNS` and `QUERY_HISTORY`).

## Enhanced Snowflake Blueprint Snippets

Substitute `<database_name>`, `<schema_name>`, and `<table_name>` dynamically based on context.

* **Discover Verified Data Assets by Domain Comment**:
```sql
SELECT table_catalog, table_schema, table_name, comment
FROM <database_name>.INFORMATION_SCHEMA.TABLES
WHERE (table_name ILIKE '%<keyword>%' OR comment ILIKE '%<keyword>%')
AND table_type = 'BASE TABLE'
ORDER BY COALESCE(comment, '') DESC;
```

* **Audit Peer Query History for Join Validation**:
```sql
SELECT query_text, user_name, execution_status
FROM TABLE(<database_name>.INFORMATION_SCHEMA.QUERY_HISTORY(RESULT_LIMIT => 100))
WHERE execution_status = 'SUCCESS'
  AND query_text ILIKE '%JOIN%'
  AND query_text ILIKE '%<target_table_name>%'
LIMIT 5;
```
