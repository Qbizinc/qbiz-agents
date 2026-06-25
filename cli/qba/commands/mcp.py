import click
import json
import yaml
from pathlib import Path
from rich.console import Console
from qba.registry import fetch_mcp_definition

console = Console()

MCP_JSON = Path(".mcp.json")


def _find_uvx() -> str:
    """Return the full resolved path to uvx."""
    import shutil
    found = shutil.which("uvx")
    if found:
        return found
    candidates = [
        Path.home() / "anaconda3" / "Scripts" / "uvx.exe",
        Path.home() / ".local" / "bin" / "uvx",
        Path.home() / ".cargo" / "bin" / "uvx",
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return "uvx"


def _substitute(value: str, env: dict) -> str:
    for key, val in env.items():
        value = value.replace(f"${{{key}}}", val).replace(f"${key}", val)
    return value


@click.group()
def mcp():
    """Manage MCP servers."""


@mcp.command("add")
@click.argument("name")
def add_mcp(name: str):
    """Install an MCP server into .mcp.json."""
    definition = fetch_mcp_definition(name)
    if not definition:
        console.print(f"[red]MCP server '{name}' not found in registry.[/red]")
        return

    config = yaml.safe_load(definition)

    # Prompt for env vars
    env_vars = config.get("env", {})
    filled_env = {}
    if env_vars:
        console.print(f"\nConfiguring [bold]{name}[/bold] MCP server:")
        for key, default in env_vars.items():
            value = click.prompt(f"  {key}", default=default or "", show_default=bool(default))
            filled_env[key] = value.strip().lstrip("﻿")

    server_name = config.get("name", name)
    mcp_type = config.get("type", "stdio")

    if mcp_type == "streamable-http":
        # HTTP-based MCP — write url + headers into .mcp.json
        url = _substitute(config.get("url", ""), filled_env)
        raw_headers = config.get("requestOptions", {}).get("headers", {})
        headers = {k: _substitute(v, filled_env) for k, v in raw_headers.items()}
        server_entry: dict = {"url": url}
        if headers:
            server_entry["headers"] = headers
    else:
        # stdio-based MCP — write command + args (+ env for env-based MCPs like Slack)
        uvx_path = _find_uvx()
        args = config.get("args", [])
        resolved_args = [_substitute(arg, filled_env) for arg in args]
        server_entry = {"command": uvx_path, "args": resolved_args}
        env_to_write = {k: v for k, v in filled_env.items() if v}
        if env_to_write:
            server_entry["env"] = env_to_write

    # Read or create .mcp.json
    if MCP_JSON.exists():
        mcp_config = json.loads(MCP_JSON.read_text())
    else:
        mcp_config = {"mcpServers": {}}

    if server_name in mcp_config["mcpServers"]:
        console.print(f"[yellow]{name} MCP already installed. Skipping.[/yellow]")
        return

    mcp_config["mcpServers"][server_name] = server_entry
    MCP_JSON.write_text(json.dumps(mcp_config, indent=2))

    console.print(f"\n[green]Installed:[/green] [bold]{name}[/bold] → .mcp.json")
    if mcp_type == "streamable-http":
        console.print(f"  url: [dim]{server_entry['url']}[/dim]")
    else:
        console.print(f"  uvx path: [dim]{server_entry['command']}[/dim]")
    console.print("\n  To skip the MCP approval prompt each session, add this to [bold].claude/settings.json[/bold]:")
    console.print('  [dim]{ "enableAllProjectMcpServers": true }[/dim]')


@mcp.command("list")
def list_mcp():
    """List installed MCP servers in this project."""
    if not MCP_JSON.exists():
        console.print("[yellow]No MCP servers installed. Run `qba agent mcp add <name>`.[/yellow]")
        return

    mcp_config = json.loads(MCP_JSON.read_text())
    servers = mcp_config.get("mcpServers", {})
    if not servers:
        console.print("[yellow]No MCP servers installed.[/yellow]")
        return

    for server_name, entry in servers.items():
        if "url" in entry:
            console.print(f"[bold cyan]{server_name}[/bold cyan] — {entry['url']}")
        else:
            console.print(f"[bold cyan]{server_name}[/bold cyan] — {entry.get('command')} {' '.join(entry.get('args', []))}")
