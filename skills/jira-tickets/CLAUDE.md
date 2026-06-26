# Claude-specific notes for jira-ticket-management

* Invoke via the Skill tool. When the `jira` MCP server is connected, its tools
  (`create_jira_ticket`, `search_jira_tickets`, `review_jira_ticket`, …) appear
  directly in your tool list — call them directly; you do not proxy through the skill.

* Always **read before write**:

  * Call `review_jira_ticket` before `add_jira_comment` to ensure you have the latest context.
  * Avoid duplicating or contradicting existing ticket information.

* `create_jira_ticket` is **idempotent at the workflow level, not the API level**:

  * Do not blindly create duplicate tickets.
  * When unsure, first call `search_jira_tickets` to check if a similar issue already exists.

* Parallelize **read-only operations** where possible:

  * `search_jira_tickets`, `list_projects`, and multiple `review_jira_ticket` calls can run in parallel.
  * Keep write operations (`create_jira_ticket`, `add_jira_comment`) **sequential and intentional**.

* Treat Jira as a **system of record**:

  * Use structured, concise comments.
  * Do not dump raw logs or unformatted data.
  * Summarize findings before writing them.

* Respect **project scoping**:

  * The MCP automatically injects the project filter in `search_jira_tickets`.
  * Do not include `project = X` in JQL unless explicitly overriding behavior.

* Handle missing or partial data:

  * Fields like `description` or `assignee` may be `None`.
  * Do not assume completeness of ticket data.

* Do not infer permissions:

  * If a tool fails, it may be due to missing Jira permissions (not model error).
  * Surface the failure clearly instead of retrying blindly.

* Avoid using Jira as a chat system:

  * Comments should represent **decisions, findings, or state changes**, not back-and-forth conversation.

* If the `jira` MCP server is not connected:

  * Instruct the user to run `qba agent mcp add jira`
  * Then restart the session before retrying
