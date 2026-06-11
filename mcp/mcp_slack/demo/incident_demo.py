"""
Agentic Incident DAG — live demo driver for the Slack MCP server.

A real Claude agent (Opus 4.8) is given the Slack MCP tools over stdio and asked
to investigate a (simulated) NovaMart pipeline failure. It autonomously decides
the tool calls: announces the incident, finds + tags + DMs the data owner, posts
diagnostic findings into the thread, pauses at a HITL approval gate before
"creating the Jira ticket", uploads a playbook, and marks the incident resolved.

Nothing here is scripted beyond the kickoff prompt — the LLM chooses every tool
call. Watch it build the Slack thread live in #qbiz_slackbot_testing.

Prerequisites:
  1. ANTHROPIC_API_KEY set in the environment.
  2. mcp_slack/.env populated with SLACK_BOT_TOKEN / SLACK_APP_TOKEN / SLACK_SIGNING_SECRET.
  3. The bot (@qbizslackbot) invited to #qbiz_slackbot_testing.
  4. For the HITL gate to resolve: the Slack app must have the `reaction_added`
     bot event subscribed (Event Subscriptions). Without it, request_approval
     simply times out and the agent proceeds noting the timeout — the rest of
     the flow still demos fine.

Run:
  uv run --with "anthropic[mcp]" python demo/incident_demo.py
"""
import asyncio
import os
import sys
from pathlib import Path

from anthropic import AsyncAnthropic
from anthropic.lib.tools.mcp import async_mcp_tool
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

MODEL = "claude-opus-4-8"
CHANNEL = "qbiz_slackbot_testing"
MCP_SLACK_DIR = Path(__file__).resolve().parent.parent  # .../mcp/mcp_slack

SYSTEM = f"""You are the Agentic Incident DAG, an autonomous on-call agent for NovaMart's
Airflow data pipelines. A pipeline has failed and you must run the full incident response
in Slack using the tools you've been given. Post everything to the #{CHANNEL} channel.

Run these steps in order, threading every follow-up under the first message:

1. Post the incident announcement (a new top-level message). Capture its `ts` — every later
   message in this incident is a threaded reply using that `ts` as `thread_ts`.
2. Find the data owner. Use find_user to look up "David Sevier" and grab their Slack user ID.
3. Tag the owner in the thread: a threaded reply containing <@USER_ID> so they get a real ping.
4. DM the owner privately with a one-line heads-up that you're investigating.
5. Post 2–3 diagnostic findings as separate threaded replies, as if the investigation is
   unfolding (e.g. checked DAG run, inspected logs, found a schema mismatch on inventory.json).
6. HITL APPROVAL GATE: before creating a Jira ticket, call request_approval in the thread asking
   "Root cause identified: schema mismatch on inventory.json. Create the Jira incident ticket?"
   with a 90 second timeout. Respect the decision: if approved, proceed; if rejected or timed out,
   post that you're holding off and stop.
7. If approved, post a final root-cause summary (threaded) including a Jira link
   (use https://qbiz.atlassian.net/browse/NOVA-4127 as a stand-in).
8. Upload a short markdown playbook file to the thread (upload_file with thread_ts).
9. Add a :white_check_mark: reaction to the original announcement message to mark it resolved.

Use Slack mrkdwn formatting (*bold*, :emoji:) and keep messages crisp and readable for a
technical data owner. Narrate briefly what you're doing as you go."""

KICKOFF = (
    "ALERT: NovaMart pipeline `novamart_inventory_sync` failed at 14:03 UTC — task "
    "`load_inventory` raised a JSON schema validation error. Run the incident response."
)


def server_params() -> StdioServerParameters:
    # Launch the Slack MCP server from its own project so its deps + .env resolve.
    return StdioServerParameters(
        command="uv",
        args=["run", "--project", str(MCP_SLACK_DIR), "slack-mcp"],
        env=dict(os.environ),
        cwd=str(MCP_SLACK_DIR),  # so the server's load_dotenv() finds mcp_slack/.env
    )


def render(message) -> None:
    """Pretty-print each turn: the agent's narration and the tool calls it makes."""
    for block in message.content:
        if block.type == "text" and block.text.strip():
            print(f"\n🤖 {block.text.strip()}")
        elif block.type == "tool_use":
            args = ", ".join(f"{k}={v!r}" for k, v in (block.input or {}).items() if k != "content")
            print(f"   ⮑  \033[36m{block.name}\033[0m({args})")


async def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY is not set.", file=sys.stderr)
        return 1

    client = AsyncAnthropic()
    print(f"Launching Slack MCP server and connecting Claude ({MODEL})…")

    async with stdio_client(server_params()) as (read, write):
        async with ClientSession(read, write) as mcp:
            await mcp.initialize()
            tools = (await mcp.list_tools()).tools
            print(f"Connected. {len(tools)} Slack tools available: "
                  f"{', '.join(t.name for t in tools)}")
            print("=" * 70)

            runner = client.beta.messages.tool_runner(
                model=MODEL,
                max_tokens=8000,
                system=SYSTEM,
                messages=[{"role": "user", "content": KICKOFF}],
                tools=[async_mcp_tool(t, mcp) for t in tools],
            )
            async for message in runner:
                render(message)

    print("\n" + "=" * 70)
    print(f"✅ Incident flow complete — see the thread in #{CHANNEL}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
