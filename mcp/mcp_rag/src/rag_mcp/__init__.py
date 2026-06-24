"""Baseline Indexed RAG MCP server.

Ingest documents, keep a persistent vector index of their contents, and keep a ledger of what
has been ingested and where it lives. Local embeddings by default; every coupling point is a
swappable module so specialists can fork without starting from scratch.
"""

__version__ = "0.1.0"
