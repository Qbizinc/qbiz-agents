"""The document ledger — a first-class record of what's been ingested and where it lives.

This is the headline feature: a queryable, human-readable answer to "what have I read, where does
it live, and is it still current" that is independent of the vector store. Persisted as a single
JSON object keyed by source.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class LedgerEntry:
    source: str          # path, URL, or "text:<title>" for raw-text ingests
    kind: str            # "file" | "url" | "text"
    title: str
    tags: list[str]
    content_hash: str
    num_chunks: int
    bytes: int
    ingested_at: str     # ISO-8601 UTC

    def to_json(self) -> dict:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Ledger:
    """JSON-backed source ledger."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._entries: dict[str, LedgerEntry] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.is_file():
            return
        data = json.loads(self._path.read_text(encoding="utf-8"))
        self._entries = {key: LedgerEntry(**value) for key, value in data.items()}

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        serialized = {key: entry.to_json() for key, entry in self._entries.items()}
        self._path.write_text(json.dumps(serialized, indent=2, ensure_ascii=False), encoding="utf-8")

    def upsert(
        self,
        *,
        source: str,
        kind: str,
        title: str,
        tags: list[str],
        content_hash: str,
        num_chunks: int,
        byte_len: int,
    ) -> LedgerEntry:
        entry = LedgerEntry(
            source=source,
            kind=kind,
            title=title,
            tags=tags,
            content_hash=content_hash,
            num_chunks=num_chunks,
            bytes=byte_len,
            ingested_at=_now(),
        )
        self._entries[source] = entry
        self._persist()
        return entry

    def get(self, source: str) -> LedgerEntry | None:
        return self._entries.get(source)

    def remove(self, source: str) -> bool:
        if source in self._entries:
            del self._entries[source]
            self._persist()
            return True
        return False

    def all(self) -> list[LedgerEntry]:
        return sorted(self._entries.values(), key=lambda entry: entry.ingested_at, reverse=True)

    def is_stale(self, source: str, current_hash: str) -> bool:
        """True if `source` is recorded but its content hash no longer matches."""
        entry = self._entries.get(source)
        return entry is not None and entry.content_hash != current_hash
