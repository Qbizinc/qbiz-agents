---
model: gemini
---

# Gemini-specific notes for snowflake-data-explorer

- Interact with the system exclusively through function tool calls to `airflow_incident_mcp`.
- **Context Bounding Constraints**: Always restrict open rows using aggregate structures or append a protective `LIMIT 50` to safeguard context limits from data dumps.
- **Structured Scannable Report Style**: Present multi-dimensional analysis or incident diagnostic insights inside highly structured markdown tables.

## Enhanced Snowflake Blueprint Snippets

Substitute `<database_name>`, `<schema_name>`, and `<table_name>` dynamically based on context.

* **Audit Schema Structural Elements**:
```sql
SELECT column_name, data_type, comment
FROM <database_name>.INFORMATION_SCHEMA.COLUMNS
WHERE table_name = '<table_name>'
AND table_schema = '<schema_name>';
```

* **Verify Pipeline Data Landing Freshness**:
```sql
SELECT 
  COUNT(*) as total_records,
  MAX(COALESCE(try_to_timestamp(column_name::string), CURRENT_TIMESTAMP())) as last_ingestion_time
FROM <database_name>.<schema_name>.<table_name>;
```

* **Exploration: Find Metrics by Keyword**:
```sql
SELECT table_schema, table_name, column_name
FROM <database_name>.INFORMATION_SCHEMA.COLUMNS
WHERE column_name ILIKE '%<metric_name>%';
```