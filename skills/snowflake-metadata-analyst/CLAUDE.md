# Claude-specific notes for snowflake-metadata-analyst

- Invoke via the Skill tool. The MCP tool (`query_snowflake_database`) is available directly in your tool list when `snowflake-managed` is connected — call it directly.
- Always use your internal `<thinking>` block to construct syntactically precise Snowflake SQL statements before calling the tool.
- Parallelize independent structural lookups (such as requesting `INFORMATION_SCHEMA.COLUMNS` and `INFORMATION_SCHEMA.TABLES` concurrently) within a single turn to save execution time.
- Use the following generalized SQL templates when querying Snowflake execution history and metadata dictionary states, substituting `<database_name>`, `<schema_name>`, and `<table_name>` with your actual target parameters:

  * **Audit Recent Failures**:
  ```sql
    SELECT query_id, query_text, error_message, start_time
    FROM TABLE(<database_name>.INFORMATION_SCHEMA.QUERY_HISTORY(RESULT_LIMIT => 20))
    WHERE execution_status = 'FAIL'
    ORDER BY start_time DESC;
  ```

* **Inspect Column Schemas**:
  ```sql
    SELECT column_name, data_type, is_nullable
    FROM <database_name>.INFORMATION_SCHEMA.COLUMNS
    WHERE table_name = '<table_name>' 
      AND table_schema = '<schema_name>';
  ```
