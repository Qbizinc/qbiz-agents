"""Source loading, chunking, and hashing.

Phase 1 keeps loaders deliberately small: local text files and plain HTTP(S) fetches. PDF / HTML
cleanup / directory ingest are Phase 2 extension points — add a branch in `load_source` and the
rest of the pipeline is unchanged.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.request import Request, urlopen

# File extensions we treat as already-plain-text.
_TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".rst", ".json", ".csv", ".tsv", ".log", ".py", ".yaml", ".yml"}

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")


def content_hash(text: str) -> str:
    """Stable content fingerprint used by the ledger to detect staleness."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _strip_html(html: str) -> str:
    """Bare-minimum HTML→text. Phase 2 should replace this with a real extractor."""
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    text = _TAG_RE.sub(" ", html)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return text


def load_source(source: str) -> tuple[str, str]:
    """Load a source into plain text.

    Args:
        source: an http(s) URL or a local file path.

    Returns:
        (text, kind) where kind is "url" or "file".

    Raises:
        FileNotFoundError / ValueError on unreadable sources.
    """
    lowered = source.lower()
    if lowered.startswith(("http://", "https://")):
        request = Request(source, headers={"User-Agent": "qbiz-rag-mcp/0.1"})
        with urlopen(request, timeout=30) as response:  # noqa: S310 - explicit user-provided URL
            charset = response.headers.get_content_charset() or "utf-8"
            raw = response.read().decode(charset, errors="replace")
            content_type = response.headers.get_content_type()
        text = _strip_html(raw) if "html" in content_type else raw
        return _normalize(text), "url"

    path = Path(source).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"No such file: {source}")
    suffix = path.suffix.lower()
    if suffix not in _TEXT_SUFFIXES and suffix not in {".htm", ".html"}:
        # Best-effort: try to read as utf-8 text; binary formats (e.g. .pdf) are Phase 2.
        raw = path.read_text(encoding="utf-8", errors="strict")
    else:
        raw = path.read_text(encoding="utf-8", errors="replace")
    text = _strip_html(raw) if suffix in {".htm", ".html"} else raw
    return _normalize(text), "file"


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WS_RE.sub(" ", text)
    # Collapse runs of blank lines to a single blank line.
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """Split text into overlapping, character-bounded chunks.

    Breaks are nudged toward the nearest paragraph or sentence boundary inside the window so chunks
    don't slice mid-sentence. Returns [] for empty input.
    """
    text = text.strip()
    if not text:
        return []
    if size <= 0:
        return [text]
    overlap = max(0, min(overlap, size - 1))

    chunks: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + size, length)
        if end < length:
            end = _nudge_boundary(text, start, end)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start = max(end - overlap, start + 1)
    return chunks


def _nudge_boundary(text: str, start: int, end: int) -> int:
    """Move `end` back to the closest paragraph/sentence break within the last 25% of the window."""
    window = end - start
    floor = start + (window * 3) // 4
    for marker in ("\n\n", ". ", "\n", " "):
        cut = text.rfind(marker, floor, end)
        if cut != -1:
            return cut + len(marker)
    return end
