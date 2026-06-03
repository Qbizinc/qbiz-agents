# Claude instructions for qbiz-agents

You are working inside the Qbiz agents repository — the central source for all reusable AI skills, MCP server definitions, and bundles.

## Structure

- `skills/<name>/` — individual skills. Each has a `SKILL.md` (model-agnostic), optional `CLAUDE.md` / `GEMINI.md` overrides, `SETUP.md`, and `OWNERS.yaml`.
- `bundles/<name>/BUNDLE.md` — groups of skills installed together.
- `mcp/mcp_<name>/mcp.yaml` — MCP server definitions.
- `checks/` — global code review rules.
- `skills-manifest.json` — auto-generated index. Never edit manually.

## Rules when working in this repo

- When adding or modifying a skill, always update `skills-manifest.json` by running `python script/generate-skills-manifest`.
- Every skill folder must contain `SKILL.md` and `OWNERS.yaml` at minimum.
- Never hardcode credentials in any file.
- Skill instructions must be model-agnostic. Put model-specific behavior in `CLAUDE.md` or `GEMINI.md` sidecars.
