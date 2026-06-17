from slack_mcp._app import mcp
from slack_mcp.slack_client import get_client, resolve_channel


@mcp.tool()
def list_channels(include_private: bool = False, limit: int = 100) -> list[dict]:
    """List Slack channels the bot has access to.

    Args:
        include_private: Include private channels the bot is a member of.
        limit: Maximum number of channels to return (capped at 1000).

    Returns:
        List of {id, name, is_private, num_members} dicts.
    """
    client = get_client()
    types = "public_channel,private_channel" if include_private else "public_channel"
    response = client.conversations_list(types=types, limit=min(limit, 1000))
    return [
        {
            "id": ch["id"],
            "name": ch["name"],
            "is_private": ch.get("is_private", False),
            "num_members": ch.get("num_members", 0),
        }
        for ch in response["channels"]
    ]


@mcp.tool()
def get_channel_history(
    channel: str,
    limit: int = 20,
    oldest: str | None = None,
) -> list[dict]:
    """Retrieve recent messages from a Slack channel.

    Args:
        channel: Channel name or ID.
        limit: Number of messages to return (max 100).
        oldest: Only return messages after this Unix timestamp string.

    Returns:
        List of {ts, user, text, thread_ts} dicts, newest first.
    """
    client = get_client()
    channel_id = resolve_channel(channel)
    kwargs: dict = {"channel": channel_id, "limit": min(limit, 100)}
    if oldest:
        kwargs["oldest"] = oldest
    response = client.conversations_history(**kwargs)
    return [
        {
            "ts": msg["ts"],
            "user": msg.get("user") or msg.get("bot_id", "unknown"),
            "text": msg.get("text", ""),
            "thread_ts": msg.get("thread_ts"),
        }
        for msg in response["messages"]
    ]
