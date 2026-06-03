import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from qba.config import SKILLS_DIR_BY_MODEL
from qba.registry import fetch_manifest, fetch_skill_files

console = Console()


@click.group()
def skills():
    """Manage skills."""


@skills.command("list")
def list_skills():
    """List available skills from the registry."""
    manifest = fetch_manifest()
    table = Table(title="Available Skills", show_lines=True)
    table.add_column("Name", style="bold cyan")
    table.add_column("Description")
    table.add_column("Roles")
    table.add_column("Requires MCP")

    for skill in manifest.get("skills", []):
        table.add_row(
            skill["name"],
            skill.get("description", ""),
            ", ".join(skill.get("roles", [])),
            ", ".join(skill.get("requires_mcp", [])) or "-",
        )
    console.print(table)


@skills.command("search")
@click.argument("query")
def search_skills(query: str):
    """Search skills by keyword."""
    manifest = fetch_manifest()
    query_lower = query.lower()
    results = [
        s for s in manifest.get("skills", [])
        if query_lower in s["name"].lower() or query_lower in s.get("description", "").lower()
    ]

    if not results:
        console.print(f"[yellow]No skills found matching '{query}'.[/yellow]")
        return

    for skill in results:
        console.print(f"[bold cyan]{skill['name']}[/bold cyan] — {skill.get('description', '')}")
        if skill.get("requires_mcp"):
            console.print(f"  Requires MCP: {', '.join(skill['requires_mcp'])}")


@skills.command("add")
@click.argument("name")
@click.option("--bundle", is_flag=True, default=False, help="Install all skills in a bundle.")
@click.option("--model", default="claude", type=click.Choice(["claude", "gemini", "both"]), help="Which model sidecar to install.")
def add_skill(name: str, bundle: bool, model: str):
    """Install a skill (or bundle) into .claude/skills/."""
    manifest = fetch_manifest()

    models = ["claude", "gemini"] if model == "both" else [model]

    if bundle:
        skill_names = _resolve_bundle(name, manifest)
        if not skill_names:
            console.print(f"[red]Bundle '{name}' not found or empty.[/red]")
            return
        for sn in skill_names:
            _install_skill(sn, manifest, models)
    else:
        _install_skill(name, manifest, models)


def _resolve_bundle(bundle_name: str, manifest: dict) -> list:
    for b in manifest.get("bundles", []):
        if b["name"] == bundle_name:
            return b.get("skills", [])
    return []


def _install_skill(name: str, manifest: dict, models: list):
    skill_entry = next((s for s in manifest.get("skills", []) if s["name"] == name), None)
    if not skill_entry:
        console.print(f"[red]Skill '{name}' not found in registry.[/red]")
        return

    files = fetch_skill_files(name, models)
    if not files:
        console.print(f"[red]Could not fetch files for skill '{name}'.[/red]")
        return

    for model in models:
        dest = SKILLS_DIR_BY_MODEL[model] / name
        if dest.exists():
            console.print(f"[yellow]{name} already installed for {model}. Skipping.[/yellow]")
            continue
        dest.mkdir(parents=True, exist_ok=True)
        for filename, content in files.items():
            (dest / filename).write_text(content)
        console.print(f"[green]Installed:[/green] [bold]{name}[/bold] → {dest}/")

    if skill_entry.get("requires_mcp"):
        console.print(f"\n  [yellow]This skill needs MCP: {', '.join(skill_entry['requires_mcp'])}[/yellow]")
        console.print(f"  Run: [bold]qba agent mcp add {skill_entry['requires_mcp'][0]}[/bold]")
