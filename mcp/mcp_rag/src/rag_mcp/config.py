"""Environment-driven configuration for the RAG MCP server.

Every tunable lives here so the rest of the package reads config, never `os.environ` directly.
Defaults are chosen so the server works out of the box with no credentials.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class RagConfig:
    data_dir: Path
    embed_backend: str
    embed_model: str
    chunk_size: int
    chunk_overlap: int
    max_results: int

    @property
    def vectors_path(self) -> Path:
        return self.data_dir / "vectors.npy"

    @property
    def chunks_path(self) -> Path:
        return self.data_dir / "chunks.jsonl"

    @property
    def ledger_path(self) -> Path:
        return self.data_dir / "ledger.json"


def load_config() -> RagConfig:
    """Read configuration from the environment, applying out-of-the-box defaults."""
    data_dir = Path(os.environ.get("RAG_DATA_DIR", ".rag")).expanduser().resolve()
    return RagConfig(
        data_dir=data_dir,
        embed_backend=os.environ.get("RAG_EMBED_BACKEND", "fastembed").strip().lower(),
        embed_model=os.environ.get("RAG_EMBED_MODEL", "BAAI/bge-small-en-v1.5").strip(),
        chunk_size=_int_env("RAG_CHUNK_SIZE", 1000),
        chunk_overlap=_int_env("RAG_CHUNK_OVERLAP", 150),
        max_results=_int_env("RAG_MAX_RESULTS", 5),
    )
