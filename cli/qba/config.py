from pathlib import Path

CLAUDE_SKILLS_DIR = Path(".claude") / "skills"
GEMINI_SKILLS_DIR = Path(".gemini") / "skills"
MCP_DIR = Path(".mcp.json")

SKILLS_DIR_BY_MODEL = {
    "claude": CLAUDE_SKILLS_DIR,
    "gemini": GEMINI_SKILLS_DIR,
}
