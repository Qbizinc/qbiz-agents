# Setup: rag-incident-memory

This skill drives the `rag` MCP server as an **incident memory**. Install the server first, then
the skill.

## 1. Install the RAG MCP server

```bash
qba agent mcp add rag
```

Accept the default config to run with local embeddings (no API key). Point `RAG_DATA_DIR` at a
**persistent, shared** path — an incident memory is only useful if it survives across runs and is
readable by everyone on-call. See [`mcp/mcp_rag/SETUP.md`](../../mcp/mcp_rag/SETUP.md) for backend
options and where the index persists. A dedicated dir (e.g. `.rag-incidents`) keeps incident records
separate from any document corpus.

## 2. Add this skill

```bash
qba agent skills add rag-incident-memory
```

## 3. Restart your session

Restart Claude Code (or your Gemini CLI session) so the MCP server connects and the skill is
discovered.

## Quick verification

Ask the agent to:
1. Record a fake incident: `ingest(text="Symptom: X. Root cause: Y. Fix: Z.", title="TEST-1",
   tags=["incident", "demo-system", "closed"])`.
2. Run `list_sources` — the incident should appear, tagged `incident` / `demo-system` / `closed`.
3. Ask it to investigate a "new" failure on `demo-system` — it should `search` the memory first and
   surface `TEST-1` as a prior occurrence.
4. `forget TEST-1` to clean up.

## Embedded / deterministic recording (no agent, no MCP)

For an automated pipeline that must record incidents **every** time (not as an agent decision),
skip the MCP server and use the engine as a library — the base `qbiz-rag-mcp` package installs
without the `mcp` dependency:

```python
from rag_mcp.index import get_index
get_index().ingest(text=report, title=ticket_key, tags=["incident", system, "open"])
```

See the "Using the engine as a library" section of [`mcp/mcp_rag/SETUP.md`](../../mcp/mcp_rag/SETUP.md).
Use this skill for interactive/on-call investigation; use library calls when recording must be
guaranteed. Both read and write the same incident memory.

## Relationship to rag-research

This skill is a domain specialization of `rag-research`. If you need a different specialized RAG,
`rag-research`'s SETUP explains the fork pattern (copy the skill folder, narrow `SKILL.md`, keep
`requires_mcp: rag`).
