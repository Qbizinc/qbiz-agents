---

name: jira-ticket-management
description: Use the Jira MCP server to create, search, review, and update Jira tickets for task tracking, incident management, and workflow automation. Use when an agent needs to interact with Jira or when setting up Jira-based tracking for a project or client. Requires the jira MCP server.
roles:
  - consultant
  - data-engineer
  - platform-engineer
requires_mcp:
  - jira

---

# Jira — Ticket Management & Workflow Automation

This skill covers the Jira MCP server: how an agent uses its tools to manage
tickets, and how to apply structured workflows for tracking work, incidents,
and analysis.

The server is **model-agnostic and reusable** — it lives in
`mcp/mcp_jira/` and requires **zero code changes** between deployments. All
environment-specific configuration is provided via environment variables.

---

## When to use this skill

* An agent needs to **create a ticket** for a bug, task, or incident.
* You need to **search or analyze existing Jira issues**.
* You want to **add structured updates or findings** to a ticket.
* You are implementing **incident tracking or auditability** for agent actions.
* A consultant is **setting up Jira integration for a client or project** — see `SETUP.md`.

---

## Tools

### Ticket creation

* `create_jira_ticket(summary, description, project_key=None, issue_type="Task")`

  * Creates a new Jira issue
  * Automatically uses the default project if none is provided
  * Validates the project before creation
  * Returns the issue key (e.g. `PROJ-123`)

---

### Search / retrieval

* `search_jira_tickets(jql=None, project_key=None, max_results=10)`

  * Searches issues using JQL (project scoping is automatic)
  * Returns `{key, summary, status}`

* `review_jira_ticket(issue_key)`

  * Fetches full issue details:

    * summary
    * description
    * status
    * assignee

* `list_projects()`

  * Lists all accessible Jira projects
  * Use when the project key is unknown or needs validation

---

### Updates

* `add_jira_comment(issue_key, comment)`

  * Adds structured updates, findings, or decisions to a ticket

---

## Core patterns

### Create → Investigate → Update

A standard agent workflow:

1. **Create ticket**

   * Use `create_jira_ticket` when an issue is detected
2. **Investigate**

   * Use logs, data, or other tools
3. **Update ticket**

   * Add findings via `add_jira_comment`
4. **Repeat until resolved**

This ensures **traceability and auditability**.

---

### Always review before updating

Before adding a comment or making a decision:

* Call `review_jira_ticket(issue_key)`
* Ensure context is up-to-date
* Avoid duplicating or contradicting existing information

---

### Use structured comments

Comments should be concise and structured:

```
[Finding]
<what was discovered>

[Impact]
<what it affects>

[Next Step]
<planned action>
```

This makes tickets readable by both humans and agents.

---

### Searching effectively (JQL patterns)

Examples:

* Open issues:

  ```
  status != Done
  ```

* Recent incidents:

  ```
  created >= -1d
  ```

* Assigned to a user:

  ```
  assignee = currentUser()
  ```

The MCP automatically injects the project filter, so do not include `project = X` manually.

---

### Incident tracking pattern

Typical flow:

1. Create incident ticket:

   * Summary: short description
   * Description: detailed context

2. Add updates during investigation:

   * Findings
   * Hypotheses
   * Data evidence

3. Final comment:

   * Root cause
   * Resolution
   * Follow-ups

---

## Message templates (for consistent ticketing)

### Ticket description

```
[Incident]
<short description>

[Context]
<system, pipeline, or dataset affected>

[Error]
<error message or symptom>

[Detected At]
<timestamp UTC>
```

---

### Investigation update

```
[Finding]
<what was discovered>

[Analysis]
<why it matters>

[Next Step]
<planned action>
```

---

### Resolution

```
[Root Cause]
<what caused the issue>

[Resolution]
<what was done>

[Follow-up]
<any future improvements>
```

---

## Gotchas (important)

* **Project scoping is enforced**

  * The MCP automatically scopes queries to a project
  * Do not include `project = X` in JQL unless overriding logic

* **Project validation is strict**

  * Invalid project keys will raise errors
  * Use `list_projects` if unsure

* **Descriptions may be empty or None**

  * Always handle missing fields when reviewing tickets

* **Permissions matter**

  * The service account must have:

    * Browse Projects
    * Create Issues
    * Add Comments

---

## Rules

* Always create a ticket for **non-trivial or recurring issues**
* Always review (`review_jira_ticket`) before commenting
* Use **structured comments** — avoid free-form dumping
* Never hardcode credentials — use environment variables / `.mcp.json`
* Treat Jira as the **source of truth** for tracking work and incidents
* If the `jira` MCP server is not connected, instruct the user to run:

  * `qba agent mcp add jira`
  * then restart the session

---

This skill enables agents to integrate with Jira for structured task tracking,
incident management, and auditable workflows.
