"""
Socket Mode listener for two-way Slack communication (Phase 10b).

Connects to Slack over a WebSocket and routes incoming events into two
in-memory queues so MCP tools can block on them:

  - ``_message_queues``  — keyed by channel ID; feeds ``wait_for_reply``.
  - ``_reaction_queues`` — keyed by ``(channel_id, message_ts)``; feeds the
    ``request_approval`` HITL gate.

Started on boot by the FastMCP lifespan in ``_app.py`` whenever
``SLACK_APP_TOKEN`` is set. If it is not set the server still runs with the
one-way posting tools; the two-way tools simply time out.
"""
import asyncio
import os
from typing import Optional


# Keyed by channel ID; each queue receives raw Slack `message`/`app_mention` events.
_message_queues: dict[str, asyncio.Queue] = {}

# Keyed by (channel_id, message_ts); each queue receives `reaction_added` events
# for that specific message. Created on demand by request_approval before it posts.
_reaction_queues: dict[tuple[str, str], asyncio.Queue] = {}

# Held so the lifespan can disconnect cleanly on shutdown.
_socket_client = None


async def start_listener() -> None:
    """Connect to Slack via Socket Mode and start routing incoming events."""
    global _socket_client

    app_token = os.environ.get("SLACK_APP_TOKEN")
    if not app_token:
        raise RuntimeError("SLACK_APP_TOKEN is not set — required for Socket Mode")
    bot_token = os.environ.get("SLACK_BOT_TOKEN")
    if not bot_token:
        raise RuntimeError("SLACK_BOT_TOKEN is not set")

    from slack_sdk.socket_mode.aiohttp import SocketModeClient
    from slack_sdk.socket_mode.response import SocketModeResponse
    from slack_sdk.socket_mode.request import SocketModeRequest
    from slack_sdk.web.async_client import AsyncWebClient

    web_client = AsyncWebClient(token=bot_token)
    socket_client = SocketModeClient(app_token=app_token, web_client=web_client)

    async def handle(sc: SocketModeClient, req: SocketModeRequest) -> None:
        if req.type == "events_api":
            event = req.payload.get("event", {})
            etype = event.get("type")

            if etype in ("message", "app_mention"):
                # Ignore the bot's own posts so an agent waiting for a human
                # reply does not capture the message it just sent.
                if not event.get("bot_id") and event.get("subtype") != "bot_message":
                    channel = event.get("channel")
                    queue = _message_queues.get(channel)
                    if queue is not None:
                        await queue.put(event)

            elif etype == "reaction_added":
                item = event.get("item", {})
                key = (item.get("channel"), item.get("ts"))
                queue = _reaction_queues.get(key)
                if queue is not None:
                    await queue.put(event)

        # Always ack, or Slack will redeliver.
        await sc.send_socket_mode_response(
            SocketModeResponse(envelope_id=req.envelope_id)
        )

    socket_client.socket_mode_request_listeners.append(handle)
    await socket_client.connect()
    _socket_client = socket_client


async def stop_listener() -> None:
    """Disconnect the Socket Mode client (called from the lifespan on shutdown)."""
    global _socket_client
    if _socket_client is not None:
        await _socket_client.disconnect()
        _socket_client = None


# --- Messages (wait_for_reply) ---------------------------------------------

def register_message_interest(channel_id: str) -> None:
    """Begin buffering messages for a channel before blocking on them."""
    _message_queues.setdefault(channel_id, asyncio.Queue())


async def wait_for_event(channel_id: str, timeout: float = 60.0) -> Optional[dict]:
    """Block until a new message arrives in channel_id, or timeout elapses.

    Returns the Slack event dict, or None on timeout.
    """
    queue = _message_queues.setdefault(channel_id, asyncio.Queue())
    try:
        return await asyncio.wait_for(queue.get(), timeout=timeout)
    except asyncio.TimeoutError:
        return None


# --- Reactions (request_approval HITL gate) --------------------------------

def register_reaction_interest(channel_id: str, ts: str) -> None:
    """Start buffering reactions for a message. Call this immediately after
    posting the prompt and before awaiting, so a fast reaction is not missed."""
    _reaction_queues.setdefault((channel_id, ts), asyncio.Queue())


async def get_reaction(channel_id: str, ts: str, timeout: float) -> Optional[dict]:
    """Wait for the next reaction on a specific message, or None on timeout.

    Does not clean up the queue — callers may loop to skip irrelevant
    reactions, then call pop_reaction_queue when done.
    """
    queue = _reaction_queues.setdefault((channel_id, ts), asyncio.Queue())
    try:
        return await asyncio.wait_for(queue.get(), timeout=timeout)
    except asyncio.TimeoutError:
        return None


def pop_reaction_queue(channel_id: str, ts: str) -> None:
    """Discard the reaction queue for a message once the gate has resolved."""
    _reaction_queues.pop((channel_id, ts), None)
