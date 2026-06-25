"""
Jira MCP Server (FastMCP Version)

Exposes Jira functionality as MCP tools:
- create ticket
- search tickets
- review ticket
- add comments
- list projects

Uses a dedicated Jira service account for attribution.
"""

import os
from jira import JIRA
from mcp.server.fastmcp import FastMCP

# ------------------------------------------------------------------------------
# MCP Server
# ------------------------------------------------------------------------------

mcp = FastMCP("jira-mcp-server")

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------

JIRA_URL = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
DEFAULT_PROJECT = os.getenv("JIRA_DEFAULT_PROJECT")

# ------------------------------------------------------------------------------
# Jira Client
# ------------------------------------------------------------------------------

jira = JIRA(
    server=JIRA_URL,
    basic_auth=(JIRA_EMAIL, JIRA_API_TOKEN)
)

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------

def resolve_project(project_key: str | None) -> str:
    return project_key if project_key else DEFAULT_PROJECT


def validate_project(project_key: str) -> None:
    valid_projects = [p.key for p in jira.projects()]
    if project_key not in valid_projects:
        raise ValueError(f"Invalid project: {project_key}")

# ------------------------------------------------------------------------------
# MCP Tools
# ------------------------------------------------------------------------------

@mcp.tool()
def create_jira_ticket(
    summary: str,
    description: str,
    project_key: str = None,
    issue_type: str = "Task"
) -> str:
    """
    Create a new Jira ticket.

    Use when:
    - user requests a new task, bug, or story
    - agent identifies an issue worth tracking

    Args:
        summary: short title of the issue
        description: detailed explanation of the issue
        project_key: Jira project key (optional, defaults to configured project)
        issue_type: Task | Bug | Story (default: Task)

    Behavior:
        - Uses default project if none provided
        - Validates project exists before creation

    Returns:
        String confirmation with Jira issue key
    """

    project = resolve_project(project_key)
    validate_project(project)

    issue = jira.create_issue(
        project=project,
        summary=summary,
        description=description,
        issuetype={"name": issue_type}
    )

    return f"Created ticket {issue.key} in project {project}"


@mcp.tool()
def search_jira_tickets(
    jql: str = None,
    project_key: str = None,
    max_results: int = 10
) -> list:
    """
    Search Jira tickets using JQL with automatic project scoping.

    Use when:
    - retrieving tickets
    - analyzing workload
    - reviewing issues

    Args:
        jql: Jira Query Language filter (WITHOUT project clause)
        project_key: optional project override
        max_results: max number of results (default 10)

    Behavior:
        - Always scopes query to a project
        - Automatically injects project filter

    Returns:
        List of tickets with key, summary, status
    """

    project = resolve_project(project_key)
    validate_project(project)

    full_jql = f"project = {project}"
    if jql:
        full_jql += f" AND ({jql})"

    issues = jira.search_issues(full_jql, maxResults=max_results)

    return [
        {
            "key": i.key,
            "summary": i.fields.summary,
            "status": i.fields.status.name
        }
        for i in issues
    ]


@mcp.tool()
def add_jira_comment(issue_key: str, comment: str) -> str:
    """
    Add a comment to a Jira ticket.

    Use when:
    - providing feedback
    - adding analysis
    - updating ticket context

    Args:
        issue_key: Jira ticket ID (e.g. PROJ-123)
        comment: structured feedback or update

    Returns:
        Confirmation string
    """

    jira.add_comment(issue_key, comment)
    return f"Added comment to {issue_key}"


@mcp.tool()
def review_jira_ticket(issue_key: str) -> dict:
    """
    Fetch detailed Jira ticket information for analysis.

    Use before:
    - commenting
    - decision making
    - generating summaries

    Args:
        issue_key: Jira ticket ID

    Returns:
        Dictionary containing:
        - key
        - summary
        - description
        - status
        - assignee
    """

    issue = jira.issue(issue_key)

    return {
        "key": issue.key,
        "summary": issue.fields.summary,
        "description": issue.fields.description,
        "status": issue.fields.status.name,
        "assignee": str(issue.fields.assignee),
    }


@mcp.tool()
def list_projects() -> list:
    """
    List all available Jira projects.

    Use when:
    - selecting project context
    - validating project keys
    - user is unsure of project name

    Returns:
        List of project keys and names
    """

    return [
        {"key": p.key, "name": p.name}
        for p in jira.projects()
    ]

# ------------------------------------------------------------------------------
# Server Entry Point
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()