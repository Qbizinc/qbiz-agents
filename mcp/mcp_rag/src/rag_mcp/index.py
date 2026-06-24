"""RagIndex — orchestrates embedder + store + ledger into the operations the tools expose.

The tool layer (`tools/rag.py`) is thin: it validates arguments and calls into here. All the RAG
behavior lives in this one class, which keeps the swappable pieces (embeddings, store, ledger)
behind a single coherent surface.
"""

from __future__ import annotations

from rag_mcp.config import RagConfig, load_config
from rag_mcp.embeddings import Embedder, get_embedder
from rag_mcp.ingest import chunk_text, content_hash, load_source
from rag_mcp.ledger import Ledger
from rag_mcp.store import Chunk, VectorStore


class RagIndex:
    def __init__(self, config: RagConfig) -> None:
        self.config = config
        config.data_dir.mkdir(parents=True, exist_ok=True)
        self._store = VectorStore(config.vectors_path, config.chunks_path)
        self._ledger = Ledger(config.ledger_path)
        self._embedder: Embedder | None = None  # built lazily on first use

    @property
    def embedder(self) -> Embedder:
        if self._embedder is None:
            self._embedder = get_embedder(self.config)
        return self._embedder

    # ---- ingest ------------------------------------------------------------

    def ingest(
        self,
        *,
        source: str | None = None,
        text: str | None = None,
        title: str | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """Ingest a file/URL (`source`) or raw `text`. Re-ingesting a source replaces its chunks."""
        tags = tags or []
        if text is not None and source is not None:
            raise ValueError("Provide either `source` or `text`, not both.")

        if text is not None:
            kind = "text"
            resolved_title = title or "untitled"
            ledger_key = f"text:{resolved_title}"
            body = text
        elif source is not None:
            body, kind = load_source(source)
            ledger_key = source
            resolved_title = title or _derive_title(source)
        else:
            raise ValueError("Provide either `source` or `text`.")

        body = body.strip()
        if not body:
            raise ValueError("Nothing to ingest — the source is empty.")

        digest = content_hash(body)
        chunks_text = chunk_text(body, self.config.chunk_size, self.config.chunk_overlap)
        if not chunks_text:
            raise ValueError("Source produced no chunks.")

        # Replace any prior copy so re-ingest is idempotent.
        self._store.delete_by_source(ledger_key)

        vectors = self.embedder.embed(chunks_text)
        chunk_objects = [
            Chunk(
                id=f"{ledger_key}::{ordinal}",
                source=ledger_key,
                ordinal=ordinal,
                text=chunk,
                metadata={"title": resolved_title, "tags": tags},
            )
            for ordinal, chunk in enumerate(chunks_text)
        ]
        self._store.add(chunk_objects, vectors)
        self._ledger.upsert(
            source=ledger_key,
            kind=kind,
            title=resolved_title,
            tags=tags,
            content_hash=digest,
            num_chunks=len(chunk_objects),
            byte_len=len(body.encode("utf-8")),
        )
        return {
            "source": ledger_key,
            "title": resolved_title,
            "kind": kind,
            "tags": tags,
            "chunks_indexed": len(chunk_objects),
            "embedding_backend": self.embedder.name,
        }

    # ---- query -------------------------------------------------------------

    def search(self, query: str, k: int | None = None, tags: list[str] | None = None) -> list[dict]:
        if not query.strip():
            raise ValueError("Query is empty.")
        k = k or self.config.max_results
        sources = self._sources_for_tags(tags) if tags else None
        if tags and not sources:
            return []
        query_vector = self.embedder.embed([query])[0]
        hits = self._store.search(query_vector, k=k, sources=sources)
        return [
            {
                "source": hit.chunk.source,
                "title": hit.chunk.metadata.get("title", ""),
                "ordinal": hit.chunk.ordinal,
                "score": round(hit.score, 4),
                "text": hit.chunk.text,
            }
            for hit in hits
        ]

    # ---- ledger views ------------------------------------------------------

    def list_sources(self) -> list[dict]:
        return [self._entry_view(entry.source) for entry in self._ledger.all()]

    def source_status(self, source: str) -> dict:
        entry = self._ledger.get(source) or self._ledger.get(f"text:{source}")
        if entry is None:
            return {"source": source, "indexed": False}
        view = self._entry_view(entry.source)
        view["indexed"] = True
        if entry.kind in {"file", "url"}:
            try:
                body, _ = load_source(entry.source)
                view["stale"] = self._ledger.is_stale(entry.source, content_hash(body.strip()))
            except (FileNotFoundError, ValueError, OSError):
                view["stale"] = None
                view["source_reachable"] = False
        else:
            view["stale"] = False  # raw text has no external source to drift from
        return view

    def forget(self, source: str) -> dict:
        key = source if self._ledger.get(source) else f"text:{source}"
        removed_chunks = self._store.delete_by_source(key)
        removed_entry = self._ledger.remove(key)
        return {"source": key, "removed": removed_entry, "chunks_removed": removed_chunks}

    def reindex(self, source: str | None = None) -> dict:
        """Re-ingest one source, or every stale file/url source when `source` is omitted."""
        if source is not None:
            entry = self._ledger.get(source) or self._ledger.get(f"text:{source}")
            if entry is None:
                raise ValueError(f"Source not in ledger: {source}")
            if entry.kind == "text":
                raise ValueError("Raw-text sources can't be reindexed — re-ingest the text.")
            result = self.ingest(source=entry.source, title=entry.title, tags=entry.tags)
            return {"reindexed": [result["source"]]}

        reindexed: list[str] = []
        for entry in self._ledger.all():
            if entry.kind not in {"file", "url"}:
                continue
            try:
                body, _ = load_source(entry.source)
            except (FileNotFoundError, ValueError, OSError):
                continue
            if self._ledger.is_stale(entry.source, content_hash(body.strip())):
                self.ingest(source=entry.source, title=entry.title, tags=entry.tags)
                reindexed.append(entry.source)
        return {"reindexed": reindexed}

    def stats(self) -> dict:
        entries = self._ledger.all()
        return {
            "sources": len(entries),
            "chunks": self._store.count(),
            "embedding_backend": self.config.embed_backend,
            "embedding_model": self.config.embed_model,
            "data_dir": str(self.config.data_dir),
        }

    # ---- helpers -----------------------------------------------------------

    def _sources_for_tags(self, tags: list[str]) -> set[str]:
        wanted = set(tags)
        return {entry.source for entry in self._ledger.all() if wanted & set(entry.tags)}

    def _entry_view(self, source: str) -> dict:
        entry = self._ledger.get(source)
        assert entry is not None
        return {
            "source": entry.source,
            "title": entry.title,
            "kind": entry.kind,
            "tags": entry.tags,
            "num_chunks": entry.num_chunks,
            "bytes": entry.bytes,
            "ingested_at": entry.ingested_at,
        }


def _derive_title(source: str) -> str:
    cleaned = source.rstrip("/")
    return cleaned.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] or source


_INDEX: RagIndex | None = None


def get_index() -> RagIndex:
    """Process-wide RagIndex singleton, mirroring the Slack MCP's get_client() pattern."""
    global _INDEX
    if _INDEX is None:
        _INDEX = RagIndex(load_config())
    return _INDEX
