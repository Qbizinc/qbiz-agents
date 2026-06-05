from dotenv import load_dotenv

load_dotenv()

from slack_mcp._app import mcp  # noqa: E402

# Importing each module registers its tools with the mcp singleton as a side effect.
import slack_mcp.tools.messaging  # noqa: F401, E402
import slack_mcp.tools.files      # noqa: F401, E402
import slack_mcp.tools.channels   # noqa: F401, E402
import slack_mcp.tools.users      # noqa: F401, E402


def main() -> None:
    mcp.run()
