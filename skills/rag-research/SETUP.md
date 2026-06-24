# Setup: rag-research

This skill drives the `rag` MCP server. Install the server first, then the skill.

## 1. Install the RAG MCP server

```bash
qba agent mcp add rag
```

Accept the default config to run with local embeddings (no API key). See
[`mcp/mcp_rag/SETUP.md`](../../mcp/mcp_rag/SETUP.md) for backend options (e.g. Gemini embeddings)
and where the index persists.

## 2. Add this skill

```bash
qba agent skills add rag-research
```

## 3. Restart your session

Restart Claude Code (or your Gemini CLI session) so the MCP server connects and the skill is
discovered.

## Quick verification

Ask the agent to:
1. Ingest a small file or URL.
2. Run `list_sources` — the document should appear in the ledger.
3. Ask a question answerable from that document — the answer should cite the source.

## Forking this skill for a specialized RAG

This skill is the template. To build a domain-specific RAG (e.g. `rag-contracts`):

1. Copy `skills/rag-research/` to `skills/<your-skill>/`.
2. In `SKILL.md`, narrow the `description` and `Rules` to your domain (what to ingest, how to
   answer, what counts as a citation). Keep `requires_mcp: rag`.
3. Only if you need different retrieval mechanics (a different embedding backend, a real vector DB,
   custom loaders), edit the corresponding module in `mcp/mcp_rag/` — each coupling point is one
   file. See [`mcp/mcp_rag/RAG_PLAN.md`](../../mcp/mcp_rag/RAG_PLAN.md).
4. Update `OWNERS.yaml`, regenerate the manifest and checksums.
