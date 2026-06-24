import sys
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from rag_mcp.config import load_config


@asynccontextmanager
async def _lifespan(_server: "FastMCP"):
    """Announce the active configuration on boot.

    The embedder itself is initialized lazily on the first ingest/search, so boot stays instant
    and credential-free even when a hosted backend is configured. We only resolve config here so
    a misconfiguration surfaces in the logs immediately rather than on first use.
    """
    config = load_config()
    config.data_dir.mkdir(parents=True, exist_ok=True)
    print(
        f"[rag-mcp] data_dir={config.data_dir} backend={config.embed_backend} "
        f"model={config.embed_model}",
        file=sys.stderr,
    )
    yield {}


mcp = FastMCP("rag-mcp", lifespan=_lifespan)
