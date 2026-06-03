import click
from qba.commands.skills import skills
from qba.commands.mcp import mcp

@click.group()
def agent():
    """Manage agents, skills, and MCP servers."""

agent.add_command(skills)
agent.add_command(mcp)
