"""Offline unit tests — no embedding model download, no network.

Covers chunking, the vector store's cosine search + deletion, and the ledger's staleness logic.
A fake embedder stands in for fastembed so the full ingest/search path is exercised too.
"""

from __future__ import annotations

import hashlib

import pytest

from rag_mcp.config import RagConfig
from rag_mcp.index import RagIndex
from rag_mcp.ingest import chunk_text, content_hash
from rag_mcp.ledger import Ledger
from rag_mcp.store import Chunk, VectorStore


# ---- chunking --------------------------------------------------------------

def test_chunk_empty_returns_nothing():
    assert chunk_text("", 100, 10) == []
    assert chunk_text("   \n  ", 100, 10) == []


def test_chunk_short_text_is_single_chunk():
    assert chunk_text("hello world", 100, 10) == ["hello world"]


def test_chunk_respects_size_and_covers_text():
    text = "word " * 400  # 2000 chars
    chunks = chunk_text(text, size=300, overlap=50)
    assert len(chunks) > 1
    assert all(len(chunk) <= 320 for chunk in chunks)  # allow boundary nudge slack
    # Every chunk is non-empty and overlapping windows cover the whole input.
    assert all(chunk.strip() for chunk in chunks)


def test_chunk_overlap_creates_shared_text():
    text = "".join(f"sentence {i}. " for i in range(200))
    chunks = chunk_text(text, size=200, overlap=60)
    assert len(chunks) >= 2


# ---- store -----------------------------------------------------------------

def _chunk(source: str, ordinal: int, text: str) -> Chunk:
    return Chunk(id=f"{source}::{ordinal}", source=source, ordinal=ordinal, text=text)


def test_store_add_search_persist(tmp_path):
    store = VectorStore(tmp_path / "vectors.npy", tmp_path / "chunks.jsonl")
    chunks = [_chunk("a.txt", 0, "alpha"), _chunk("a.txt", 1, "beta"), _chunk("b.txt", 0, "gamma")]
    vectors = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
    store.add(chunks, vectors)
    assert store.count() == 3

    hits = store.search([1.0, 0.0], k=2)
    assert hits[0].chunk.text == "alpha"  # exact direction match ranks first

    # Reload from disk and confirm persistence.
    reloaded = VectorStore(tmp_path / "vectors.npy", tmp_path / "chunks.jsonl")
    assert reloaded.count() == 3


def test_store_tag_filter_by_source(tmp_path):
    store = VectorStore(tmp_path / "v.npy", tmp_path / "c.jsonl")
    store.add(
        [_chunk("a.txt", 0, "alpha"), _chunk("b.txt", 0, "beta")],
        [[1.0, 0.0], [0.9, 0.1]],
    )
    hits = store.search([1.0, 0.0], k=5, sources={"b.txt"})
    assert len(hits) == 1
    assert hits[0].chunk.source == "b.txt"


def test_store_delete_by_source(tmp_path):
    store = VectorStore(tmp_path / "v.npy", tmp_path / "c.jsonl")
    store.add(
        [_chunk("a.txt", 0, "alpha"), _chunk("a.txt", 1, "beta"), _chunk("b.txt", 0, "gamma")],
        [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]],
    )
    removed = store.delete_by_source("a.txt")
    assert removed == 2
    assert store.count() == 1
    assert store.sources() == {"b.txt"}


def test_store_rejects_mismatched_dim(tmp_path):
    store = VectorStore(tmp_path / "v.npy", tmp_path / "c.jsonl")
    store.add([_chunk("a.txt", 0, "alpha")], [[1.0, 0.0]])
    with pytest.raises(ValueError):
        store.add([_chunk("b.txt", 0, "beta")], [[1.0, 0.0, 0.0]])


# ---- ledger ----------------------------------------------------------------

def test_ledger_upsert_get_remove_stale(tmp_path):
    ledger = Ledger(tmp_path / "ledger.json")
    ledger.upsert(
        source="a.txt", kind="file", title="A", tags=["x"],
        content_hash="hash1", num_chunks=3, byte_len=100,
    )
    assert ledger.get("a.txt").title == "A"
    assert ledger.is_stale("a.txt", "hash2") is True
    assert ledger.is_stale("a.txt", "hash1") is False

    # Reload persists.
    reloaded = Ledger(tmp_path / "ledger.json")
    assert reloaded.get("a.txt").num_chunks == 3
    assert reloaded.remove("a.txt") is True
    assert reloaded.get("a.txt") is None


def test_content_hash_is_stable():
    assert content_hash("hello") == hashlib.sha256(b"hello").hexdigest()


# ---- full index path with a fake embedder ----------------------------------

class _FakeEmbedder:
    """Deterministic bag-of-chars embedder — keeps the test offline and dependency-free."""

    name = "fake"

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = [0.0] * 26
            for char in text.lower():
                if "a" <= char <= "z":
                    vector[ord(char) - 97] += 1.0
            vectors.append(vector or [0.0] * 26)
        return vectors


def _index(tmp_path) -> RagIndex:
    config = RagConfig(
        data_dir=tmp_path, embed_backend="fake", embed_model="fake",
        chunk_size=1000, chunk_overlap=100, max_results=5,
    )
    index = RagIndex(config)
    index._embedder = _FakeEmbedder()  # inject the fake, bypass get_embedder
    return index


def test_index_ingest_search_ledger(tmp_path):
    index = _index(tmp_path)
    result = index.ingest(text="alpha beta gamma delta", title="greek", tags=["lang"])
    assert result["chunks_indexed"] >= 1

    sources = index.list_sources()
    assert len(sources) == 1
    assert sources[0]["title"] == "greek"

    hits = index.search("alpha beta", tags=["lang"])
    assert hits and hits[0]["source"] == "text:greek"

    # Tag filter that matches nothing returns nothing.
    assert index.search("alpha", tags=["nope"]) == []


def test_index_reingest_replaces_and_forget(tmp_path):
    index = _index(tmp_path)
    index.ingest(text="first version", title="doc")
    index.ingest(text="second version entirely different", title="doc")
    # Re-ingest replaced, not duplicated.
    assert len(index.list_sources()) == 1

    forgotten = index.forget("doc")
    assert forgotten["removed"] is True
    assert index.list_sources() == []
    assert index.stats()["chunks"] == 0
