import os
import re
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Slack user IDs look like U0123ABCD / W0123ABCD (enterprise). find_user returns
# these, and agents commonly pass them straight back into send_dm.
_USER_ID_RE = re.compile(r"[UW][A-Z0-9]{8,}$")

# Cache channel name -> ID. conversations.list is a low-rate-limit method, and an
# agent posting many messages to one channel would otherwise call it every time.
_channel_cache: dict[str, str] = {}

_client: WebClient | None = None


def get_client() -> WebClient:
    global _client
    if _client is None:
        token = os.environ.get("SLACK_BOT_TOKEN")
        if not token:
            raise RuntimeError("SLACK_BOT_TOKEN is not set")
        _client = WebClient(token=token)
    return _client


def resolve_channel(name_or_id: str) -> str:
    """Resolve a channel name (with or without #) to a channel ID."""
    name_or_id = name_or_id.strip()
    # Looks like a channel ID already (C followed by uppercase letters/digits, e.g. C01234ABCDE)
    import re
    if re.fullmatch(r"C[A-Z0-9]{6,}", name_or_id):
        return name_or_id
    name = name_or_id.lstrip("#")
    if name in _channel_cache:
        return _channel_cache[name]
    client = get_client()
    cursor = None
    while True:
        kwargs: dict = {"types": "public_channel,private_channel", "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        response = client.conversations_list(**kwargs)
        for ch in response["channels"]:
            if ch["name"] == name:
                _channel_cache[name] = ch["id"]
                return ch["id"]
        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    raise ValueError(f"Channel not found: {name_or_id!r}")


def resolve_user_id(query: str) -> str:
    """Resolve a display name, real name, email, or user ID to a Slack user ID."""
    query = query.strip()
    # Already a Slack user ID (e.g. as returned by find_user) — use it directly.
    if _USER_ID_RE.fullmatch(query):
        return query
    client = get_client()
    # Try email lookup first — fastest path
    if "@" in query:
        try:
            response = client.users_lookupByEmail(email=query)
            return response["user"]["id"]
        except SlackApiError:
            pass  # Fall through to name search
    q = query.lower()
    cursor = None
    while True:
        kwargs: dict = {"limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        response = client.users_list(**kwargs)
        for user in response["members"]:
            if user.get("deleted") or user.get("is_bot"):
                continue
            profile = user.get("profile", {})
            if (
                q in user.get("name", "").lower()
                or q in user.get("real_name", "").lower()
                or q in profile.get("display_name", "").lower()
            ):
                return user["id"]
        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    raise ValueError(f"User not found: {query!r}")
