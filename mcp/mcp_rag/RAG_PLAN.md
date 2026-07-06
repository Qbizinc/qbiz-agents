# RAG MCP Server — Implementation Plan

## Overview

A reusable Model Context Protocol (MCP) server that gives any MCP-compatible agent a
**baseline Indexed RAG** capability: ingest documents, keep a persistent vector index of their
contents, and keep a human-readable **ledger of what has been ingested and where it lives**.

It is two things at once:

1. **Usable out of the box** — `qba agent mcp add rag`, no API key required. Documents in,
   grounded retrieval out, with a queryable record of every source.
2. **A template for consultants** — the engine is small, dependency-light, and every coupling
   point (embedding backend, vector store, chunking, loaders) is a single swappable module. A
   consultant building a specialized RAG (contracts, support tickets, a client's data catalog)
   forks the thin behavior layer (the `rag-research` skill) and, if needed, swaps one module here
   — they never start from scratch.

**Design goals:**
- Self-contained Python package — drop into any project via config, not code.
- Zero required credentials for the default path (local embeddings).
- The "what have I read / where does it live / is it stale" ledger is a first-class, queryable
  artifact, not a side effect of the vector store.
- Every provider/storage coupling is isolated behind a small interface so specialists can swap it.
- The server does **no LLM generation** — it only embeds and retrieves. The reasoning model
  (Claude or Gemini) stays entirely on the host side. This keeps it genuinely model-agnostic and
  sidesteps the open QBiz LLM-provider question, which only touches the host, not this server.

---

## Architecture

```
mcp/mcp_rag/
├── RAG_PLAN.md            ← this file
├── mcp.yaml              ← install/run definition for `qba agent mcp add rag`
├── pyproject.toml        ← package: qbiz-rag-mcp, entry point rag-mcp
├── README.md             ← develop & test locally
├── SETUP.md             ← prerequisites + how to add to a project
├── src/rag_mcp/
│   ├── __init__.py
│   ├── _app.py          ← FastMCP singleton (+ data-dir lifespan)
│   ├── server.py        ← imports tool modules, defines main()
│   ├── config.py        ← env-driven RagConfig
│   ├── embeddings.py    ← Embedder protocol + FastEmbed (default) + Gemini (example)
│   ├── ingest.py        ← source loaders (file/url/raw) + chunking + hashing
│   ├── store.py         ← VectorStore — persistent cosine index (numpy-backed)
│   ├── ledger.py        ← Ledger — the "what's ingested & where" record
│   ├── index.py         ← RagIndex — orchestrates the above; get_index() singleton
│   └── tools/
│       ├── __init__.py
│       └── rag.py       ← MCP tool definitions
└── tests/
    └── test_chunk_unit.py  ← offline unit tests (no embedder, no network)
```

### The two-layer split (why MCP **and** a skill)

| Concern | Lives in | Why |
|---|---|---|
| Ingest / embed / store / **ledger of sources** | this MCP server (`mcp/mcp_rag/`) | Persistent state behind tools — exactly what MCP is for. |
| *When* to ingest, *when* to retrieve, how to cite, keeping the ledger honest | `skills/rag-research/` | Model-agnostic behavior; the **fork point** for specialists. |

This mirrors the repo's existing pattern: `airflow-pipeline-doctor` (skill) + `astro-airflow` (MCP).

---

## Tools

| Tool | Purpose |
|---|---|
| `ingest` | Ingest a file path, URL, or raw text. Chunks, embeds, stores, and records the source in the ledger. Re-ingest replaces the prior copy. |
| `search` | Semantic search over all ingested content. Returns passages with source + score, optionally filtered by tag. |
| `list_sources` | The ledger: every ingested source, where it lives, when it was read, chunk count, tags, freshness. |
| `source_status` | Is a specific source indexed? Is it stale (content changed since ingest)? |
| `forget` | Remove a source's chunks from the index and the ledger. |
| `reindex` | Re-ingest a source (or all stale sources) to refresh changed content. |
| `stats` | Index-wide counts: sources, chunks, embedding backend/model, data dir. |

All tools operate on the `RagIndex` singleton, which lazily initializes the embedder on first use
(so server boot stays instant and key-free until the first ingest/search).

---

## Key design decisions

### Embeddings — local by default, pluggable (`embeddings.py`)
- **Default:** [`fastembed`](https://github.com/qdrant/fastembed) with `BAAI/bge-small-en-v1.5`.
  ONNX-based, no `torch`, no API key — small enough to ship through `uvx`. This is what makes the
  server work out of the box.
- **Swap point:** `Embedder` is a tiny protocol (`embed(texts) -> vectors`, `dim`, `name`).
  `get_embedder(config)` dispatches on `RAG_EMBED_BACKEND`. A lazy-imported `GeminiEmbedder` is
  included as a worked example of a hosted backend (relevant given QBiz's likely Gemini
  subscription) — it activates only when `RAG_EMBED_BACKEND=gemini` and a key is present.

### Vector store — transparent baseline, documented upgrade path (`store.py`)
- **Default:** a numpy-backed persistent cosine store (`vectors.npy` + `chunks.jsonl`). Vectors are
  L2-normalized on add, so search is a single normalized dot product + top-k. Deliberately
  hand-rolled and ~150 lines: a consultant can read the whole thing, and it's plenty for the
  document volumes a baseline RAG starts with.
- **Upgrade path (documented, not built):** the store is one module with a narrow surface
  (`add`, `search`, `delete_by_source`, `count`). Swapping in Chroma / LanceDB / pgvector for scale
  is a single-file change that touches nothing else.

### Ledger — a first-class artifact (`ledger.py`)
The headline feature. A JSON record (`ledger.json`) keyed by source, holding `title`, `tags`,
`content_hash`, `num_chunks`, `ingested_at`, `bytes`, and `kind` (file/url/text). It answers "what
have I read, where does it live, and is it still current" without touching the vector store, and is
what `list_sources` / `source_status` expose. Staleness = stored `content_hash` ≠ a fresh hash of
the source.

### Persistence layout (`RAG_DATA_DIR`, default `./.rag`)
```
.rag/
├── vectors.npy     # (N, dim) float32, L2-normalized
├── chunks.jsonl    # one JSON per chunk: {id, source, ordinal, text, metadata}
└── ledger.json     # the source ledger
```
Per-project by default, so two projects don't share an index. Override with `RAG_DATA_DIR`.

### Packaging — engine-only base, server as an extra (`pyproject.toml`)

The engine (`index` / `store` / `embeddings` / `ingest` / `ledger` / `config`) imports only
`numpy` + `fastembed`; `mcp` and `python-dotenv` live solely in the server layer (`_app` / `server`
/ `tools`). So the base install carries **no MCP dependency**:

- `pip install qbiz-rag-mcp` → engine only. An embedded consumer does `from rag_mcp.index import
  get_index` and ingests/searches directly (e.g. an Airflow task — this is what the
  novamart-pipelines incident-memory integration uses).
- `pip install 'qbiz-rag-mcp[server]'` → adds `mcp` + `python-dotenv` and the `rag-mcp` entry
  point. This is what `mcp.yaml` / `qba agent mcp add rag` install.

(Extras can only *add* dependencies, so making the base engine-only is the only way to let a library
consumer avoid `mcp` — hence server-as-extra rather than an "engine" subset.)

---

## Configuration (env, surfaced in `mcp.yaml`)

| Var | Default | Meaning |
|---|---|---|
| `RAG_DATA_DIR` | `./.rag` | Where the index + ledger persist. |
| `RAG_EMBED_BACKEND` | `fastembed` | `fastembed` (local) or `gemini` (hosted example). |
| `RAG_EMBED_MODEL` | `BAAI/bge-small-en-v1.5` | Embedding model id for the chosen backend. |
| `RAG_CHUNK_SIZE` | `1000` | Target chunk size in characters. |
| `RAG_CHUNK_OVERLAP` | `150` | Overlap between consecutive chunks, in characters. |
| `RAG_MAX_RESULTS` | `5` | Default `k` for `search`. |
| `GEMINI_API_KEY` | — | Only read when `RAG_EMBED_BACKEND=gemini`. |

---

## Build phases

- **Phase 1 — Baseline engine (this scaffold).** FastEmbed default, numpy store, ledger, all seven
  tools, offline unit test, packaging + `mcp.yaml`, the `rag-research` skill template.
- **Phase 2 — Loaders.** Broaden `ingest.py`: PDF (`pypdf`), HTML cleanup, directory/glob ingest,
  basic CSV/JSON handling.
- **Phase 3 — Scale swap.** Provide an alternative `store.py` backed by LanceDB or pgvector behind
  the same interface; document the env-selected switch. Design for the pgvector backend (including
  the ledger-must-also-move subtlety and an env-selected `get_store` factory) is written up in
  [`PGVECTOR_STORE_PLAN.md`](./PGVECTOR_STORE_PLAN.md) — planned, not yet built.
- **Phase 4 — Specialization examples.** Ship one forked skill (e.g. `rag-contracts`) as a worked
  example of the template path, plus a bundle entry.

---

## Out of scope (deliberately)

- LLM generation / answer synthesis — that's the host agent's job; this server only retrieves.
- Re-ranking, hybrid (BM25 + vector) search, query expansion — Phase 3+ extension points.
- Auth / multi-tenant isolation beyond per-project `RAG_DATA_DIR`.

---

## Repository context

Lives in [`qbiz-agents`](https://github.com/Qbizinc/qbiz-agents) at `mcp/mcp_rag/`, alongside the
Slack and Airflow MCPs. Registered in the `qba` CLI registry so consultants install it with
`qba agent mcp add rag`. Self-contained: also usable standalone via
`uvx --from git+https://github.com/Qbizinc/qbiz-agents.git#subdirectory=mcp/mcp_rag rag-mcp`.
