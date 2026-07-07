# rag-mcp

Baseline **Indexed RAG** MCP server for Qbiz agents. Ingest documents, keep a persistent vector
index of their contents, and keep a queryable **ledger of what's been read and where it lives**.

- **Out of the box:** local embeddings via `fastembed` — no API key required.
- **A template:** every coupling point (embeddings, vector store, loaders, chunking) is one small,
  swappable module. Fork the behavior in [`skills/rag-research`](../../skills/rag-research/) for a
  specialized RAG without starting from scratch.

See [RAG_PLAN.md](RAG_PLAN.md) for the full design and roadmap.

## Tools

| Tool | What it does |
|---|---|
| `ingest` | Ingest a file path, URL, or raw text. Chunks, embeds, stores, records in the ledger. |
| `search` | Semantic search over indexed content; returns passages with `source` + score. |
| `list_sources` | The ledger — every source, where it lives, when read, chunk count, tags. |
| `source_status` | Is a source indexed? Has it gone stale (content changed since ingest)? |
| `forget` | Remove a source from the index and the ledger. |
| `reindex` | Re-ingest one source, or all stale sources, to refresh changed content. |
| `stats` | Index-wide counts + active embedding backend/model. |

## Configuration

All via environment variables (see [mcp.yaml](mcp.yaml)):

| Var | Default | Meaning |
|---|---|---|
| `RAG_DATA_DIR` | `.rag` | Where the index + ledger persist (per project). |
| `RAG_EMBED_BACKEND` | `fastembed` | `fastembed` (local) or `gemini` (hosted example). |
| `RAG_EMBED_MODEL` | `BAAI/bge-small-en-v1.5` | Embedding model id. |
| `RAG_CHUNK_SIZE` | `1000` | Target chunk size (characters). |
| `RAG_CHUNK_OVERLAP` | `150` | Overlap between chunks (characters). |
| `RAG_MAX_RESULTS` | `5` | Default `k` for `search`. |

> Changing the embedding model changes the vector dimension. Clear `RAG_DATA_DIR` before
> re-ingesting under a new model.

## Develop & test locally

```bash
cd mcp/mcp_rag
uv sync                      # install deps into a local .venv
uv run pytest                # offline unit tests (chunking, store, ledger)
uv run rag-mcp               # run the server over stdio
```

Smoke-test the engine without the MCP layer:

```bash
uv run python -c "from rag_mcp.index import RagIndex; from rag_mcp.config import load_config; \
i = RagIndex(load_config()); \
print(i.ingest(text='The mitochondria is the powerhouse of the cell.', title='bio')); \
print(i.search('what makes energy in a cell?')); \
print(i.list_sources())"
```

The first `ingest`/`search` downloads the embedding model (~90 MB for the default) and caches it.

## Install into a project

```bash
qba agent mcp add rag
```

This writes the server config to your project's `.mcp.json`. See [SETUP.md](SETUP.md).

## Extending (the template path)

- **Embeddings** — add a class with the `Embedder` shape in `embeddings.py` and a branch in
  `get_embedder`. A hosted `GeminiEmbedder` is included as a worked example.
- **Vector store** — `store.py` exposes `add` / `search` / `delete_by_source` / `count`. Swap in
  Chroma / LanceDB / pgvector behind that surface; nothing else changes.
- **Loaders** — extend `load_source` in `ingest.py` for PDFs, HTML extraction, directories, etc.
