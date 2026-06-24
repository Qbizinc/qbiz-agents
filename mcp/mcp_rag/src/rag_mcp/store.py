"""Persistent cosine vector store — the transparent baseline backend.

Deliberately hand-rolled and small so a consultant can read the whole thing. Vectors are
L2-normalized on add, so search is a single normalized dot product + top-k. For larger corpora,
swap this module for Chroma / LanceDB / pgvector behind the same four-method surface
(`add`, `search`, `delete_by_source`, `count`) — nothing else in the package needs to change.

Persistence:
    vectors.npy   (N, dim) float32, L2-normalized, row-aligned with chunks.jsonl
    chunks.jsonl  one JSON object per row: {id, source, ordinal, text, metadata}
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class Chunk:
    id: str
    source: str
    ordinal: int
    text: str
    metadata: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "ordinal": self.ordinal,
            "text": self.text,
            "metadata": self.metadata,
        }

    @classmethod
    def from_json(cls, data: dict) -> "Chunk":
        return cls(
            id=data["id"],
            source=data["source"],
            ordinal=data["ordinal"],
            text=data["text"],
            metadata=data.get("metadata", {}),
        )


@dataclass
class SearchHit:
    chunk: Chunk
    score: float


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


class VectorStore:
    """In-memory cosine index with append-only JSONL + npy persistence."""

    def __init__(self, vectors_path: Path, chunks_path: Path) -> None:
        self._vectors_path = vectors_path
        self._chunks_path = chunks_path
        self._chunks: list[Chunk] = []
        self._vectors: np.ndarray | None = None  # (N, dim) float32, normalized
        self._load()

    # ---- persistence -------------------------------------------------------

    def _load(self) -> None:
        if self._chunks_path.is_file():
            with self._chunks_path.open("r", encoding="utf-8") as handle:
                self._chunks = [Chunk.from_json(json.loads(line)) for line in handle if line.strip()]
        if self._vectors_path.is_file():
            self._vectors = np.load(self._vectors_path).astype(np.float32)
        if self._vectors is not None and len(self._vectors) != len(self._chunks):
            # Defensive: persisted files disagree. Start clean rather than serve bad matches.
            self._chunks = []
            self._vectors = None

    def _persist(self) -> None:
        self._vectors_path.parent.mkdir(parents=True, exist_ok=True)
        with self._chunks_path.open("w", encoding="utf-8") as handle:
            for chunk in self._chunks:
                handle.write(json.dumps(chunk.to_json(), ensure_ascii=False) + "\n")
        if self._vectors is None or len(self._vectors) == 0:
            self._vectors_path.unlink(missing_ok=True)
        else:
            np.save(self._vectors_path, self._vectors)

    # ---- mutation ----------------------------------------------------------

    def add(self, chunks: list[Chunk], vectors: list[list[float]]) -> int:
        """Append chunks and their (un-normalized) vectors. Returns the new total count."""
        if not chunks:
            return self.count()
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must be the same length")
        new = _normalize_rows(np.asarray(vectors, dtype=np.float32))
        if self._vectors is None:
            self._vectors = new
        else:
            if new.shape[1] != self._vectors.shape[1]:
                raise ValueError(
                    f"Embedding dim {new.shape[1]} != existing {self._vectors.shape[1]}. "
                    "The index was built with a different model — clear RAG_DATA_DIR to rebuild."
                )
            self._vectors = np.vstack([self._vectors, new])
        self._chunks.extend(chunks)
        self._persist()
        return self.count()

    def delete_by_source(self, source: str) -> int:
        """Drop every chunk belonging to `source`. Returns the number removed."""
        keep = [i for i, chunk in enumerate(self._chunks) if chunk.source != source]
        removed = len(self._chunks) - len(keep)
        if removed == 0:
            return 0
        self._chunks = [self._chunks[i] for i in keep]
        self._vectors = self._vectors[keep] if self._vectors is not None and keep else None
        self._persist()
        return removed

    # ---- query -------------------------------------------------------------

    def search(self, query_vector: list[float], k: int, sources: set[str] | None = None) -> list[SearchHit]:
        """Top-k cosine matches, optionally restricted to a set of sources."""
        if self._vectors is None or not self._chunks:
            return []
        query = np.asarray(query_vector, dtype=np.float32)
        norm = np.linalg.norm(query)
        if norm == 0:
            return []
        query = query / norm
        scores = self._vectors @ query  # cosine, both sides normalized

        candidate_idx = np.arange(len(self._chunks))
        if sources is not None:
            mask = np.array([chunk.source in sources for chunk in self._chunks])
            candidate_idx = candidate_idx[mask]
            if candidate_idx.size == 0:
                return []
            scores = scores[candidate_idx]

        top = min(k, candidate_idx.size)
        order = np.argsort(-scores)[:top]
        return [SearchHit(chunk=self._chunks[int(candidate_idx[i])], score=float(scores[i])) for i in order]

    # ---- introspection -----------------------------------------------------

    def count(self) -> int:
        return len(self._chunks)

    def sources(self) -> set[str]:
        return {chunk.source for chunk in self._chunks}
