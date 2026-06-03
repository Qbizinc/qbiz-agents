# Global Code Review Rules

These rules apply to all PRs across all Qbiz repos.

## General
- No hardcoded credentials, API keys, or passwords in any file.
- No `.env` files committed to git.
- All new skills must have a `SKILL.md` with valid frontmatter (name, description, roles).
- `skills-manifest.json` must be regenerated before merging any skill addition or change.
- `checksums.sha256` must be regenerated before merging any skill or MCP change.
- `OWNERS.yaml` must be present in every new skill folder.

## MCP definitions (`mcp/`)
PRs touching `mcp/` require extra scrutiny — MCP definitions run code on the user's machine.

- The `command` field must only reference well-known, audited package managers: `uvx`, `npx`, `python`, `node`. No absolute paths, no inline scripts.
- The `args` field must not contain shell operators (`&&`, `|`, `;`, `$()`, backticks).
- Any new MCP must have a linked public source repo so reviewers can verify what it does.
- Requires approval from at least two members of `qbiz/platform` before merging.

## Skills (`skills/`)
- Skill instructions must not ask the model to exfiltrate data, delete files, or bypass security controls.
- Skills that require MCP must list them explicitly in `requires_mcp` frontmatter.
- Model-specific instructions (`CLAUDE.md`, `GEMINI.md`) must not contradict the model-agnostic `SKILL.md`.
