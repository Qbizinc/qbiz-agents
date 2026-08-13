# Gemini instructions for qbiz-agents

You are working inside the Qbiz agents repository — the central source for all reusable AI skills, MCP server definitions, and bundles.

## Structure

- `skills/<name>/` — individual skills. Each has a `SKILL.md` (model-agnostic), optional `CLAUDE.md` / `GEMINI.md` overrides, `SETUP.md`, and `OWNERS.yaml`.
- `bundles/<name>/BUNDLE.md` — groups of skills installed together.
- `mcp/mcp_<name>/mcp.yaml` — MCP server definitions.
- `checks/` — global code review rules.
- `personas/<Name>.md` — reusable role definitions (Architect, Engineer, Challenger) for design and
  review work. Read `personas/AGENTS.md` before writing an ad hoc review persona from scratch.
- `skills-manifest.json` — auto-generated index. Never edit manually.

## Rules when working in this repo

- When adding or modifying a skill, always update `skills-manifest.json` by running `python script/generate-skills-manifest`.
- Every skill folder must contain `SKILL.md` and `OWNERS.yaml` at minimum.
- Never hardcode credentials in any file — see `SECURITY.md` for the full policy. Tests
  that need secret-shaped strings must assemble them at runtime (see
  `assay/tests/conftest.py::planted_secret_line`), never as committed literals; the only
  directory allowed to hold fake credential literals is `assay/demo/fixtures/` (allowlisted
  in `.gitguardian.yaml`).
- Skill instructions must be model-agnostic. Put model-specific behavior in `CLAUDE.md` or `GEMINI.md` sidecars.
- **DRY applies across the whole repo, not just within one tool.** These tools (skills, MCP servers, `harness/`, `assay/`, the `rag` MCP, …) are meant to compose and support one another. Before building a new capability inside one tool, check whether it's actually generic infrastructure another tool would need: a new external-system integration belongs in a new or extended `mcp/mcp_<name>/` server, a new cross-cutting enforcement primitive belongs in `harness/`, a persistent/queryable store belongs behind the `rag` MCP. Build or extend the shared tool and consume it from there, rather than duplicating the logic inside the specific tool that first needed it — even when building the shared tool first is more work up front. See `assay/ASSAY_PLAN.md`'s "Reuse over duplication" section for a worked example.
