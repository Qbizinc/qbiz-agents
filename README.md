# qbiz-agents

The central repository for all Qbiz AI agents, skills, and MCP server definitions. Skills are model-agnostic and work with both **Claude** and **Gemini**.

---

## What is this?

This repo is the single source of truth for reusable AI capabilities across Qbiz projects. Instead of every project reinventing the same prompts and agent workflows, teams install skills from here and get consistent, maintained behavior across all models.

Skills in this repo follow the [Agent Skills open specification](https://github.com/anthropics/skills) — the standard introduced by Anthropic and adopted by 32+ tools including Claude Code, Gemini CLI, Cursor, VS Code, GitHub Copilot, and others. This means skills built here are portable across AI tools out of the box.

```
qbiz-agents/
├── skills/                    # Individual skills (code-review, sql-analyst, etc.)
│   └── <skill-name>/
│       ├── SKILL.md           # Model-agnostic definition + instructions
│       ├── CLAUDE.md          # Claude-specific overrides (optional)
│       ├── GEMINI.md          # Gemini-specific overrides (optional)
│       ├── SETUP.md           # Prerequisites and API keys needed
│       └── OWNERS.yaml        # PR review routing
├── bundles/                   # Grouped skill collections (e.g. data-team, backend)
│   └── <bundle-name>/
│       └── BUNDLE.md
├── mcp/                       # MCP server definitions (Slack, Snowflake, etc.)
│   └── mcp_<name>/
├── checks/                    # Global code review rules applied across all repos
├── agents/                    # Long-running, autonomous agent definitions
├── cli/                       # Source for the `qba` Python CLI
│   ├── pyproject.toml
│   └── qba/
│       ├── main.py
│       └── commands/
├── tools/                     # Internal build tooling for contributors (skill linter, scaffolding, CI helpers)
├── script/                    # Repo maintenance scripts (manifest + checksum generation) — not skill scripts
├── skills-manifest.json       # Auto-generated index of all skills (do not edit)
├── CLAUDE.md                  # Repo-level instructions for Claude
└── GEMINI.md                  # Repo-level instructions for Gemini
```

---

## How others use this

### 1. Install the CLI

The `qba` CLI is how you interact with this repo. Install it globally with `pipx` (recommended) or `pip`:

```bash
# Recommended: isolated install
pipx install qba-agents

# Or with pip
pip install qba-agents
```

> **No Python environment needed in your project.** Install `qba` once, then run it from any project folder to install skills and MCP configs there.

---

### 2. Initialize your project

In the root of any project where you want to use Qbiz skills:

```bash
qba agent init
```

This creates a `.agents/` folder in your project with a local config:

```
your-project/
└── .agents/
    ├── config.yaml       # Which model to target (claude | gemini)
    ├── skills/           # Installed skills live here
    └── mcp/              # MCP server configs for this project
```

You'll be prompted to choose your model:

```
? Which AI model are you targeting?
  > claude
    gemini
    both
```

---

### 3. Add skills to your project

```bash
# Add a single skill
qba agent skills add code-review

# Add an entire bundle (e.g. all data-team skills)
qba agent skills add --bundle data-team

# Search for available skills
qba agent skills search sql

# List all installed skills
qba agent skills list
```

Skills are pulled from this repo and copied into your project's `.agents/skills/` folder. If you chose `claude`, the `CLAUDE.md` override is injected. If `gemini`, the `GEMINI.md` override is used instead.

---

### 4. Add MCP servers

```bash
# Add an MCP server definition
qba agent mcp add snowflake

# List installed MCP servers
qba agent mcp list
```

---

### 5. Run a skill directly

```bash
# Invoke a skill against your model
qba agent run code-review
```

---

## How skills work with Claude vs Gemini

Every skill has a **model-agnostic core** in `SKILL.md`. Model-specific behavior lives in optional sidecar files:

| File | Purpose |
|---|---|
| `SKILL.md` | Core instructions, always loaded |
| `CLAUDE.md` | Claude-specific tool references, prompt tuning |
| `GEMINI.md` | Gemini-specific tool references, prompt tuning |
| `SETUP.md` | One-time setup steps (API keys, dependencies) |

When you run `qba agent skills add <name>`, the CLI knows which sidecar to install based on your `config.yaml` target. If you target `both`, all files are installed.

---

## Building your own skill

A skill is just a folder with markdown files. Minimum required: `SKILL.md`.

```
skills/my-skill/
├── SKILL.md       ← required: what the skill does and how to run it
├── CLAUDE.md      ← optional: Claude-specific tuning
├── GEMINI.md      ← optional: Gemini-specific tuning
├── SETUP.md       ← optional: prerequisites, one-time setup steps
└── OWNERS.yaml    ← optional: who reviews PRs for this skill
```

**`SKILL.md` frontmatter:**
```markdown
---
name: my-skill
description: One sentence — what this skill does and when to use it.
roles:
  - data-engineer
requires_mcp:
  - my-server        # if the skill needs an MCP
---
```

The `description` is the most important field — it's what the model reads to decide if the skill applies to the user's request.

See [skills/TEMPLATE/](skills/TEMPLATE/) for a full starter template.

---

## Building your own MCP server (FastMCP / stdio)

All custom MCP servers in this repo use [FastMCP](https://github.com/jlowin/fastmcp) and run as local stdio processes — the same pattern as `astro-airflow-mcp`.

**Folder structure:**
```
mcp/mcp_my_server/
├── mcp.yaml             ← tells qba how to install and start this server
├── pyproject.toml       ← Python package definition
├── src/
│   └── my_server/
│       ├── __init__.py
│       └── server.py    ← FastMCP server code
└── README.md            ← how to develop and test locally
```

**`server.py` — minimal FastMCP example:**
```python
from fastmcp import FastMCP

mcp = FastMCP("My Server")

@mcp.tool()
def my_tool(input: str) -> str:
    """Does something useful."""
    return f"Result: {input}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

**`pyproject.toml` — make it installable via uvx:**
```toml
[project]
name = "qbiz-my-server"
version = "0.1.0"
dependencies = ["fastmcp"]

[project.scripts]
qbiz-my-server = "my_server.server:mcp.run"
```

**`mcp.yaml` — so `qba agent mcp add` can install it:**
```yaml
name: my-server
description: What this server does.
command: uvx
args:
  - qbiz-my-server
  - --transport
  - stdio
env: {}
tools:
  - my_tool
```

**How someone else uses it:**
```bash
qba agent mcp add my-server
```
That's it. `uvx` downloads and runs the package — no manual install needed.

---

## Agents

`agents/` is for long-running, autonomous agent definitions — workflows that run without constant user interaction, coordinate multiple skills and MCP servers, and are designed to operate over extended periods or on a schedule.

Unlike skills (which are invoked by the user for a specific task), agents are meant to:
- Run continuously or on a cron schedule
- Chain multiple skills together autonomously
- React to events (a failed DAG, a Slack message, a new PR)
- Report back when something needs human attention

**Example:** a `pipeline-guardian` agent that monitors Airflow every 15 minutes, runs `airflow-pipeline-doctor` when failures are detected, traces lineage with a `dbt-explorer` skill, and posts a summary to Slack — all without a human in the loop.

Agent definitions live in `agents/<name>/` and follow a similar structure to skills, with an `AGENT.md` describing the agent's goal, triggers, tools, and escalation behavior.

---

## Internal tooling

`tools/` and `script/` are for contributors working inside this repo — not for end users.

| Folder | Purpose |
|---|---|
| `script/` | Repo maintenance scripts — `generate-skills-manifest` and `generate-checksums`. These are for keeping this repo's index and security files up to date, not for skills themselves. Scripts that belong to a specific skill live inside that skill's folder under `skills/<name>/`. |
| `tools/` | Structured internal tooling — skill linter, scaffolding helpers, CI validators. Lives here when a script grows complex enough to need its own package or tests. |

---

## Contributing a skill or MCP

1. Fork this repo and create a branch
2. Add your skill under `skills/<name>/` or MCP under `mcp/mcp_<name>/`
3. Regenerate the manifest: `python script/generate-skills-manifest`
4. Regenerate checksums: `python script/generate-checksums`
5. Open a PR

---

## Environment and prerequisites

### For users of skills

| Requirement | Why |
|---|---|
| `pipx` or `pip` | To install the `qba` CLI |
| Claude Code CLI | If targeting Claude (`claude` must be in PATH) |
| Gemini CLI | If targeting Gemini (`gemini` must be in PATH) |
| API keys | Set in your model's own config, not here |

The `qba` CLI does **not** manage your Claude or Gemini API keys — those stay in your model's own configuration (e.g. `~/.claude/` or `~/.gemini/`).

### For contributors to this repo

```bash
# Clone and set up dev environment
git clone https://github.com/Qbizinc/qbiz-agents
cd qbiz-agents
pip install -e "cli/[dev]"

# Install the pre-commit hook (regenerates skills-manifest.json on commit)
pip install pre-commit
pre-commit install
```

---

## Key files

| File | What it is |
|---|---|
| `skills-manifest.json` | Auto-generated index the CLI uses to discover skills. Never edit manually. |
| `CLAUDE.md` | Repo-level operating instructions when Claude works inside this repo |
| `GEMINI.md` | Repo-level operating instructions when Gemini works inside this repo |
| `checks/review.md` | Global code review rules applied across all Qbiz repos |
| `OWNERS.yaml` | Root-level PR reviewer assignments |

---

## CLI internals

The `qba` CLI lives in `cli/` and is built with [Click](https://click.palletsprojects.com/) and [Rich](https://github.com/Textualize/rich).

```
cli/
├── pyproject.toml          # Package definition — entry point: qba = qba.main:cli
└── qba/
    ├── main.py             # Root CLI group
    ├── config.py           # Reads .agents/config.yaml, resolves model + paths
    ├── registry.py         # Fetches skills-manifest.json and skill files from GitHub
    └── commands/
        ├── agent.py        # `qba agent` group — wires subcommands together
        ├── init.py         # `qba agent init` — scaffolds .agents/, writes CLAUDE.md/GEMINI.md
        ├── skills.py       # `qba agent skills list/search/add`
        ├── mcp.py          # `qba agent mcp add/list`
        └── run.py          # `qba agent run <skill>` — invokes claude/gemini CLI
```

**How skill installation works:**
1. `registry.py` fetches `skills-manifest.json` from the main branch of this repo
2. Finds the requested skill entry and downloads its files from `skills/<name>/`
3. Reads `.agents/config.yaml` to know which model sidecar to install (`CLAUDE.md` or `GEMINI.md`)
4. Writes all files into `.agents/skills/<name>/`
5. If the skill requires an MCP, prints a reminder to run `qba agent mcp add <name>`

**How MCP installation works:**
1. `registry.py` fetches `mcp/mcp_<name>/mcp.yaml` from this repo
2. Prompts the user for any required env vars (e.g. `AIRFLOW_URL`, credentials)
3. Auto-detects the full path to `uvx` on the user's machine
4. Substitutes credential values directly into the args (no separate env section)
5. Writes the final config to `.mcp.json` at the project root — the file Claude Code reads for MCP servers

**How Claude picks up installed skills:**
- Skills installed into `.claude/skills/<name>/` are automatically discovered by Claude Code at session start — no `CLAUDE.md` changes needed
- The `SKILL.md` description is injected into context so Claude knows when to apply the skill

---

## Available skills

| Skill | Description | Requires MCP |
|---|---|---|
| `airflow-pipeline-doctor` | Identifies broken Airflow pipelines — failed DAG runs, import errors, stuck queues | `astro-airflow` |

---

## Available MCP servers

| Name | Description |
|---|---|
| `astro-airflow` | Apache Airflow via Astronomer's `astro-airflow-mcp` — DAGs, runs, tasks, logs |

---

## Quick reference

```bash
qba agent init                              # Initialize a project
qba agent skills list                       # List available skills from registry
qba agent skills search <query>             # Search skills by keyword
qba agent skills add <name>                 # Install a skill
qba agent skills add --bundle <name>        # Install a bundle of skills
qba agent mcp add <name>                    # Install an MCP server → writes to .mcp.json
qba agent mcp list                          # List installed MCP servers from .mcp.json
python script/generate-skills-manifest      # Regenerate skills-manifest.json (contributors)
python script/generate-checksums            # Regenerate checksums.sha256 (contributors)
```
