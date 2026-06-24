"""MCP tool surface for the RAG server.

Thin wrappers over `RagIndex` — argument shaping and docstrings the model reads, nothing more.
All behavior lives in `rag_mcp.index`.
"""

from rag_mcp._app import mcp
from rag_mcp.index import get_index


@mcp.tool()
def ingest(
    source: str | None = None,
    text: str | None = None,
    title: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Ingest a document into the index and record it in the ledger.

    Provide exactly one of `source` or `text`. Re-ingesting the same source replaces its prior
    copy, so this is safe to call repeatedly.

    Args:
        source: A local file path or an http(s) URL to read.
        text: Raw text to ingest directly (use instead of `source`).
        title: Human-friendly label; defaults to the filename/URL tail, or "untitled" for text.
        tags: Optional labels for later filtering in `search`.

    Returns:
        A summary: {source, title, kind, tags, chunks_indexed, embedding_backend}.
    """
    return get_index().ingest(source=source, text=text, title=title, tags=tags)


@mcp.tool()
def search(query: str, k: int | None = None, tags: list[str] | None = None) -> list[dict]:
    """Semantically search the ingested content.

    Args:
        query: Natural-language query.
        k: Max passages to return (defaults to RAG_MAX_RESULTS).
        tags: If given, restrict results to sources carrying any of these tags.

    Returns:
        Ranked passages: [{source, title, ordinal, score, text}], best first. Cite `source` when
        you use a passage in an answer.
    """
    return get_index().search(query, k=k, tags=tags)


@mcp.tool()
def list_sources() -> list[dict]:
    """List every ingested document — the ledger of what's been read and where it lives.

    Returns:
        [{source, title, kind, tags, num_chunks, bytes, ingested_at}], most recent first.
    """
    return get_index().list_sources()


@mcp.tool()
def source_status(source: str) -> dict:
    """Report whether a source is indexed and whether it has gone stale.

    A source is stale when its current content no longer matches the hash recorded at ingest time.

    Args:
        source: The file path, URL, or title used at ingest.

    Returns:
        {source, indexed, ...ledger fields..., stale}. `stale` is null if the source can't be
        re-read to compare.
    """
    return get_index().source_status(source)


@mcp.tool()
def forget(source: str) -> dict:
    """Remove a source from both the index and the ledger.

    Args:
        source: The file path, URL, or title used at ingest.

    Returns:
        {source, removed, chunks_removed}.
    """
    return get_index().forget(source)


@mcp.tool()
def reindex(source: str | None = None) -> dict:
    """Refresh changed content by re-ingesting.

    Args:
        source: Re-ingest this one source. If omitted, re-ingest every file/url source that has
            gone stale. Raw-text sources are skipped (re-ingest the text directly).

    Returns:
        {reindexed: [sources that were refreshed]}.
    """
    return get_index().reindex(source)


@mcp.tool()
def stats() -> dict:
    """Index-wide counts and active configuration.

    Returns:
        {sources, chunks, embedding_backend, embedding_model, data_dir}.
    """
    return get_index().stats()
