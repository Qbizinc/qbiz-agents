from dotenv import load_dotenv

load_dotenv()

from rag_mcp._app import mcp  # noqa: E402

# Importing the tool module registers its tools with the mcp singleton as a side effect.
import rag_mcp.tools.rag  # noqa: F401, E402


def main() -> None:
    mcp.run()
