---
model: gemini
---

# Gemini-specific notes for snowflake-metadata-analyst

- The MCP tool `query_snowflake_database` is available via the connected `snowflake-managed` server — call it as a function.
- Bound all diagnostic queries with an explicit `LIMIT 50` or summary aggregates to keep context windows clear and prevent massive data dumps.
- Focus query log evaluations on the specific failure exception type and the relevant statement string.
- Use the following generalized SQL templates when retrieving table data state and freshness updates, substituting `<database_name>`, `<schema_name>`, and `<table_name>` with your actual target parameters:

  * **Verify Data Freshness (Null Upstream Check)**:
  ```sql
    SELECT COUNT(*) as row_count, MAX(<timestamp_column>) as last_ingested_record
    FROM <database_name>.<schema_name>.<table_name>;
  ```

* **Check Warehouse Processing Status**:
  ```sql
    SELECT query_type, warehouse_name, execution_time, error_message
    FROM TABLE(<database_name>.INFORMATION_SCHEMA.QUERY_HISTORY())
    WHERE execution_status = 'FAIL'
    LIMIT 10;
  ```
