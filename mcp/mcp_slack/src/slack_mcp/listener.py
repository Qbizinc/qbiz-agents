"""
Socket Mode listener for two-way Slack communication (Phase 10b).

Provides infrastructure for receiving Slack events and surfacing them to the MCP
server via a wait_for_reply tool. Not wired into server.py yet — implement after
the core posting tools are verified working end-to-end.
"""
import asyncio
import os
from typing import Optional


# Keyed by channel ID; each queue receives raw Slack event dicts.
_message_queues: dict[str, asyncio.Queue] = {}


async def start_listener() -> None:
    """Connect to Slack via Socket Mode and start routing incoming events."""
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
            if event.get("type") in ("message", "app_mention"):
                channel = event.get("channel")
                if channel and channel in _message_queues:
                    await _message_queues[channel].put(event)
        await sc.send_socket_mode_response(
            SocketModeResponse(envelope_id=req.envelope_id)
        )

    socket_client.socket_mode_request_listeners.append(handle)
    await socket_client.connect()


async def wait_for_event(channel_id: str, timeout: float = 60.0) -> Optional[dict]:
    """Block until a new message arrives in channel_id, or timeout elapses.

    Returns the Slack event dict, or None on timeout.
    """
    if channel_id not in _message_queues:
        _message_queues[channel_id] = asyncio.Queue()
    try:
        return await asyncio.wait_for(_message_queues[channel_id].get(), timeout=timeout)
    except asyncio.TimeoutError:
        return None
