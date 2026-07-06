# pgvector Store Backend — Design Plan (not yet implemented)

## Status

**Planned, not built.** This documents the design for a Postgres/pgvector-backed vector store so the
RAG engine can persist to a shared database instead of local numpy files. Referenced from
`RAG_PLAN.md` Phase 3 ("Scale swap"). The forcing function is the novamart-pipelines incident-memory
integration (`novamart-pipelines/RAG_INCIDENT_MEMORY_PLAN.md`): multiple Airflow workers need to
**read and write one shared incident memory concurrently**, which the single-process numpy store
can't do — and novamart already runs Postgres in its Astro stack, so pgvector adds no new infra.

## Why pgvector (vs. the numpy baseline)

| | numpy store (today) | pgvector store (this plan) |
|---|---|---|
| Persistence | local files (`vectors.npy`, `chunks.jsonl`) | shared Postgres database |
| Concurrent writers | no (one process owns the files) | yes (transactional) |
| Cross-worker/-host | no | yes |
| Scale | fine to ~10⁴–10⁵ chunks in memory | large corpora, ANN index |
| Infra cost | none | a Postgres with the `vector` extension |

The numpy store stays the **default** (zero-infra, out-of-the-box). pgvector is an opt-in backend.

## The interface to satisfy

The rest of the package touches the store through exactly this surface (`store.py` today). A
pgvector store must implement the same, so nothing else changes:

```python
class VectorStore:
    def add(self, chunks: list[Chunk], vectors: list[list[float]]) -> int   # returns new total count
    def delete_by_source(self, source: str) -> int                          # returns rows removed
    def search(self, query_vector: list[float], k: int,
               sources: set[str] | None = None) -> list[SearchHit]          # top-k cosine, optional source filter
    def count(self) -> int
    def sources(self) -> set[str]
```

with the existing `Chunk(id, source, ordinal, text, metadata)` and `SearchHit(chunk, score)` shapes.
Notes on current semantics the pgvector version must preserve:

- **Vectors are L2-normalized on add**; search is cosine (both sides normalized). pgvector's `<=>`
  (cosine distance) gives this directly — `score = 1 - distance`.
- **`add` enforces a fixed embedding dim** — a dim mismatch is an error telling the user to clear the
  store (a model change). pgvector's `vector(N)` column enforces this at the DB level; surface the
  same friendly error.
- **`delete_by_source` then `add`** is how re-ingest replaces a source (idempotent). Keep that; do
  the delete+insert in **one transaction** so a concurrent reader never sees a half-replaced source.
- **`sources` filter** is the only filter the store sees — tags are resolved to a source set by the
  ledger *before* `search` is called, so the store just needs `WHERE source = ANY(:sources)`.

## Enabling refactor (small, in `index.py`)

Today `RagIndex.__init__` constructs `VectorStore(config.vectors_path, config.chunks_path)`
directly. To make the backend env-selectable rather than a code edit, introduce a factory:

```python
def get_store(config: RagConfig) -> VectorStore:      # dispatch on config.store_backend
    if config.store_backend == "pgvector":
        from rag_mcp.stores.pgvector import PgVectorStore
        return PgVectorStore(config)
    from rag_mcp.stores.numpy import NumpyVectorStore   # today's store.py, renamed/moved
    return NumpyVectorStore(config.vectors_path, config.chunks_path)
```

Lazy-import the pgvector store so its dependency isn't required unless selected (same pattern as the
Gemini embedder). This is the only change outside the new module.

## Schema

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS rag_chunks (
    id        TEXT PRIMARY KEY,          -- Chunk.id  ("<source>::<ordinal>")
    source    TEXT NOT NULL,             -- Chunk.source (the ledger key)
    ordinal   INT  NOT NULL,
    text      TEXT NOT NULL,
    metadata  JSONB NOT NULL DEFAULT '{}',   -- {title, tags}
    embedding VECTOR(:dim) NOT NULL       -- dim fixed at first create; L2-normalized on write
);

CREATE INDEX IF NOT EXISTS rag_chunks_source_idx ON rag_chunks (source);
-- ANN index for search (cosine). ivfflat needs ANALYZE + a lists tuning; hnsw is simpler to operate.
CREATE INDEX IF NOT EXISTS rag_chunks_embedding_idx
    ON rag_chunks USING hnsw (embedding vector_cosine_ops);
```

Table/schema names namespaced via config (below) so one Postgres can host several independent
indexes (e.g. `rag-incidents` vs a document corpus) without collision.

## Operation → SQL mapping

| Method | SQL |
|---|---|
| `add` | `INSERT INTO rag_chunks (...) VALUES (...)` (batch, `execute_values`); normalize vectors client-side first |
| `delete_by_source` | `DELETE FROM rag_chunks WHERE source = :source` (returns `rowcount`) |
| `search` | `SELECT id, source, ordinal, text, metadata, 1 - (embedding <=> :q) AS score FROM rag_chunks [WHERE source = ANY(:sources)] ORDER BY embedding <=> :q LIMIT :k` |
| `count` | `SELECT count(*) FROM rag_chunks` |
| `sources` | `SELECT DISTINCT source FROM rag_chunks` |

Re-ingest = `delete_by_source(source)` + `add(...)` wrapped in a single transaction.

## ⚠️ The ledger also has to move (don't miss this)

The vector store is only half the persistence. The **ledger** (`ledger.py` → `ledger.json`) is a
separate local-file artifact that backs `list_sources`, `source_status`, staleness (`content_hash`),
and — critically — **tag→source resolution for filtered search**. If the store moves to shared
Postgres but the ledger stays a per-process JSON file, then in a multi-worker deployment:

- a record written by worker A is invisible to worker B's `list_sources` / tag search;
- tag-scoped `search` silently returns nothing on workers that didn't do the ingest.

So a pgvector deployment needs a **shared ledger too**. Two options:

- **(Recommended) A companion `rag_sources` table** mirroring the ledger fields (`source` PK,
  `kind`, `title`, `tags JSONB`, `content_hash`, `num_chunks`, `ingested_at`, `byte_len`), written in
  the same transaction as the chunk delete+insert. Add a `Ledger` backend behind the same interface
  `ledger.py` exposes (`upsert`, `all`, `get`, `delete`), selected by the same `RAG_STORE_BACKEND`.
- Derive the ledger from `rag_chunks` (source + metadata + counts). Rejected: `content_hash`,
  `ingested_at`, and `byte_len` aren't recoverable from chunks, so staleness/freshness would break.

Treat "pgvector backend" as **store + ledger**, both Postgres-backed and both written in one
transaction, or the shared-memory guarantees don't actually hold.

## Configuration (new env, added to `config.py` + `mcp.yaml`)

| Var | Default | Meaning |
|---|---|---|
| `RAG_STORE_BACKEND` | `numpy` | `numpy` (files) or `pgvector` (Postgres) |
| `RAG_PG_DSN` | — | Postgres connection string; required when backend is `pgvector` |
| `RAG_PG_SCHEMA` | `public` | Schema to hold the tables |
| `RAG_PG_TABLE_PREFIX` | `rag` | Prefix so multiple indexes coexist (`rag_chunks`, `rag_sources`) |

`data_dir` is ignored when the backend is `pgvector`.

## Dependency (new extra)

```toml
[project.optional-dependencies]
pgvector = ["psycopg[binary]>=3.1", "pgvector>=0.2"]
```

Consistent with the engine-only base: `pip install 'qbiz-rag-mcp[pgvector]'` (add `server` too if
running the MCP server). Lazy-imported in the pgvector store module so the base install never needs it.

## Bootstrap / migration

- On first `PgVectorStore(config)`, run `CREATE EXTENSION IF NOT EXISTS vector` + `CREATE TABLE IF
  NOT EXISTS ...` (idempotent). `CREATE EXTENSION` needs a role with privilege — document that the
  DB/extension may be pre-provisioned by an admin (Astro's local Postgres allows it; managed
  Postgres may not).
- Dim is fixed at table creation. Changing the embedding model ⇒ the `vector(N)` width no longer
  matches ⇒ drop/recreate the table (the store surfaces the same "clear and rebuild" error the numpy
  store gives on a dim mismatch).

## Testing

- **Unit:** the SQL builders and vector normalization — no DB. Assert the emitted SQL/params for
  each method, and that re-ingest issues delete+insert in one transaction.
- **Integration:** against a real pgvector (a `pgvector/pgvector` container or the Astro Postgres).
  Mark it `live`/`pg` like the existing embedding-download tests so it's excluded by default. Run the
  **same behavioral suite** the numpy store passes (round-trip add/search, source filter, re-ingest
  replaces, dim-mismatch error, concurrent writer) against both backends to prove interface parity.

## Out of scope (for this backend)

- Pushing tag filters into SQL (metadata JSONB queries) — current behavior resolves tags → sources
  in the ledger first, so it isn't needed for parity; a later efficiency option.
- Hybrid (BM25 + vector) search, re-ranking — `RAG_PLAN.md` Phase 3+ items, backend-independent.
- Non-Postgres vector DBs (LanceDB/Chroma) — the same `get_store` seam would host them; separate plan.
- Auth/multi-tenant beyond schema/table-prefix namespacing.
