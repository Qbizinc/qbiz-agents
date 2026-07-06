# Setup: rag-mcp

## Prerequisites

- `uvx` must be installed and accessible (bundled with `uv`):
  ```bash
  pip install uv
  # or
  pipx install uv
  ```
  Verify with: `uvx --version`

- **No API key needed** for the default local embedding backend.

## Adding the MCP to your project

```bash
qba agent mcp add rag
```

This will:
1. Prompt you for the config values (all have working defaults — accept them to run locally).
2. Auto-detect your `uvx` path.
3. Write the config to `.mcp.json` in your project root.

The first `ingest` or `search` downloads the embedding model (~90 MB for the default
`BAAI/bge-small-en-v1.5`) and caches it under your uv cache. Subsequent runs are fast.

## Where your index lives

By default the index and ledger persist to `.rag/` in your project root:

```
.rag/
├── vectors.npy     # the embeddings
├── chunks.jsonl    # the indexed passages
└── ledger.json     # what's been ingested and where it lives
```

Add `.rag/` to your `.gitignore` unless you intend to commit the index. Point `RAG_DATA_DIR` at a
shared path to reuse one index across projects.

## Using the engine as a library (embedded, no MCP)

The base package is **engine-only** — you can ingest and search directly from Python without the
MCP server or the `mcp` dependency. This is the path for embedding RAG inside another system (e.g.
an Airflow task):

```bash
# Base install pulls only the engine deps (numpy, fastembed) — no `mcp`.
pip install 'qbiz-rag-mcp @ git+https://github.com/Qbizinc/qbiz-agents.git#subdirectory=mcp/mcp_rag'
```

```python
import os
os.environ["RAG_DATA_DIR"] = "/some/persistent/path"   # config is read from the environment
from rag_mcp.index import get_index

get_index().ingest(text=record, title=ticket_key, tags=["incident", dag_id, "open"])
hits = get_index().search(f"{dag_id} {symptom}", tags=["incident", dag_id])
```

The engine reads all configuration from environment variables (`RAG_DATA_DIR`, `RAG_EMBED_BACKEND`,
`RAG_CHUNK_SIZE`, …) — set them before the first `get_index()` call. To run the **MCP server**
instead, install the server extra: `pip install 'qbiz-rag-mcp[server]'` (this is what `mcp.yaml`
and `qba agent mcp add rag` do for you).

## Using a hosted embedding backend (optional)

To use Google Gemini embeddings instead of the local model:

1. Install the optional extra (if running standalone): `uv pip install 'qbiz-rag-mcp[gemini]'`
2. Set in your `.mcp.json` env:
   ```
   RAG_EMBED_BACKEND=gemini
   RAG_EMBED_MODEL=text-embedding-004
   GEMINI_API_KEY=<your key>
   ```

If you switch backends/models on an existing index, clear `RAG_DATA_DIR` first — vector dimensions
must match.

## Skipping the approval prompt (optional)

By default, Claude Code asks you to approve the MCP server once per session. To skip this, add to
your project's `.claude/settings.json`:

```json
{ "enableAllProjectMcpServers": true }
```

## Restart required

After running `qba agent mcp add`, restart your Claude Code session for the MCP to connect.
