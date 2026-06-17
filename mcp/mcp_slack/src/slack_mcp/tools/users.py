from slack_mcp._app import mcp
from slack_mcp.slack_client import get_client


@mcp.tool()
def find_user(query: str) -> list[dict]:
    """Search for Slack users by name, display name, or email.

    Performs substring matching against name, real name, and display name.
    Passes email directly to the Slack lookup API for an exact match.

    Args:
        query: Partial or full name, display name, or email address.

    Returns:
        List of matching {id, name, real_name, display_name, email} dicts.
    """
    client = get_client()
    q = query.lower()
    matches: list[dict] = []
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
            name = user.get("name", "").lower()
            real_name = user.get("real_name", "").lower()
            display_name = profile.get("display_name", "").lower()
            email = profile.get("email", "").lower()
            if q in name or q in real_name or q in display_name or q == email:
                matches.append({
                    "id": user["id"],
                    "name": user.get("name", ""),
                    "real_name": user.get("real_name", ""),
                    "display_name": profile.get("display_name", ""),
                    "email": email,
                })
        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return matches
