import click
from qba.commands.agent import agent

@click.group()
@click.version_option(package_name="qba-agents")
def cli():
    """qba — Qbiz AI agents CLI."""

cli.add_command(agent)
