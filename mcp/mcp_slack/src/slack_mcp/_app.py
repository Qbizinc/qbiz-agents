import os
import sys
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP


@asynccontextmanager
async def _lifespan(_server: "FastMCP"):
    """Start the Socket Mode listener on boot when SLACK_APP_TOKEN is set.

    Without the token the server still runs with the one-way posting tools;
    the two-way HITL tools simply time out. A connection failure is logged but
    does not prevent the server from starting.
    """
    started = False
    if os.environ.get("SLACK_APP_TOKEN"):
        from slack_mcp import listener
        try:
            await listener.start_listener()
            started = True
            print("[slack-mcp] Socket Mode listener connected.", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 — degrade, don't crash boot
            print(f"[slack-mcp] Socket Mode listener failed to start: {exc}", file=sys.stderr)
    else:
        print("[slack-mcp] SLACK_APP_TOKEN not set — HITL tools disabled.", file=sys.stderr)

    try:
        yield {}
    finally:
        if started:
            from slack_mcp import listener
            await listener.stop_listener()


mcp = FastMCP("slack-mcp", lifespan=_lifespan)
