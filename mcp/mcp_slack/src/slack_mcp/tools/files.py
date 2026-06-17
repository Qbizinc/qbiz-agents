import base64
from slack_mcp._app import mcp
from slack_mcp.slack_client import get_client, resolve_channel


@mcp.tool()
def upload_file(
    channel: str,
    filename: str,
    content: str,
    title: str | None = None,
    initial_comment: str | None = None,
    thread_ts: str | None = None,
    is_base64: bool = False,
) -> str:
    """Upload a file to a Slack channel.

    Args:
        channel: Channel name or ID to share the file in.
        filename: Name for the uploaded file (e.g. "playbook.md").
        content: File content as a plain string, or base64-encoded bytes
            when is_base64 is True.
        title: Optional display title shown in Slack above the file.
        initial_comment: Optional message posted alongside the file.
        thread_ts: Post the file as a reply in this thread.
        is_base64: Set True when content is base64-encoded binary data.

    Returns:
        The file permalink URL.
    """
    client = get_client()
    channel_id = resolve_channel(channel)

    kwargs: dict = {
        "channel": channel_id,
        "filename": filename,
        "title": title or filename,
    }
    if initial_comment:
        kwargs["initial_comment"] = initial_comment
    if thread_ts:
        kwargs["thread_ts"] = thread_ts

    if is_base64:
        kwargs["file"] = base64.b64decode(content)
    else:
        kwargs["content"] = content

    response = client.files_upload_v2(**kwargs)
    return response["file"]["permalink"]
