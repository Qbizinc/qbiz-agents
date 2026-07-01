---
model: gemini
---

# Gemini-specific notes for jira-ticket-management

- Call Jira tools directly via function calls — do not narrate or simulate tool output.
- **Read before write**: always call `review_jira_ticket` before `add_jira_comment` to avoid contradicting existing ticket context.
- **Parallel reads**: `search_jira_tickets`, `list_projects`, and multiple `review_jira_ticket` calls can be issued in parallel in a single turn.
- **Structured output**: format comments and ticket descriptions using the templates in SKILL.md. Do not dump raw logs or unformatted text into Jira.
- If a tool call fails due to permissions, surface the error clearly — do not retry silently.
- If the `jira` MCP server is not connected, instruct the user to run `qba agent mcp add jira` and restart the session.
