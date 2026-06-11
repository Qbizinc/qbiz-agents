"""
Agentic Incident DAG — SCRIPTED demo driver (no LLM required).

Same incident story as incident_demo.py, but a deterministic script decides the
tool calls instead of a live model. It launches the Slack MCP server over stdio,
lists its tools, and invokes them through the real MCP protocol in the incident
order — so this genuinely demonstrates the MCP server's tool surface, not a
bypass. The HITL approval gate is fully live: the script posts the prompt and
blocks until a human reacts in Slack.

Use this when no LLM provider/key is available. The only thing missing vs. the
LLM version is that a human wrote the sequence; every tool call is real.

Prereqs: mcp_slack/.env populated, and @qbizslackbot invited to the channel.
No ANTHROPIC_API_KEY needed.

Run:
  uv run python demo/incident_demo_scripted.py

Env knobs (optional):
  DEMO_CHANNEL       channel name              (default qbiz_slackbot_testing)
  DEMO_OWNER         data owner to find/tag    (default "David Sevier")
  APPROVAL_TIMEOUT   seconds to await reaction (default 90)
  STEP_DELAY         pause between steps, secs (default 1.5)
"""
import asyncio
import json
import os
from datetime import timedelta
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

MCP_SLACK_DIR = Path(__file__).resolve().parent.parent
CHANNEL = os.environ.get("DEMO_CHANNEL", "qbiz_slackbot_testing")
OWNER = os.environ.get("DEMO_OWNER", "David Sevier")
APPROVAL_TIMEOUT = int(os.environ.get("APPROVAL_TIMEOUT", "90"))
STEP_DELAY = float(os.environ.get("STEP_DELAY", "1.5"))

PLAYBOOK = """# Runbook — novamart_inventory_sync schema failures

1. Confirm the upstream `inventory.json` contract in the data catalog.
2. Diff the failing payload against the expected schema (see Airflow logs).
3. If a field type changed, coordinate with the source team before backfilling.
4. Re-run `load_inventory` once the contract is aligned; verify row counts.
"""


def _text(result) -> str:
    for block in result.content:
        if getattr(block, "type", None) == "text":
            return block.text
    return ""


async def call(session: ClientSession, name: str, *, _timeout: int | None = None, **args):
    """Invoke an MCP tool and return its real return value.

    FastMCP exposes typed returns (-> str, -> list[dict]) in `structuredContent`,
    wrapping primitives/lists as {"result": value}. Untyped `-> dict` tools
    (request_approval, wait_for_reply) get no structuredContent, so we fall back
    to JSON-parsing the text block. We only reach that fallback when
    structuredContent is absent, so a typed `ts` string never gets mis-parsed.
    """
    kwargs = {}
    if _timeout is not None:
        kwargs["read_timeout_seconds"] = timedelta(seconds=_timeout)
    result = await session.call_tool(name, args, **kwargs)
    if result.isError:
        raise RuntimeError(f"{name} failed: {_text(result)}")
    sc = result.structuredContent
    if sc is not None:
        if isinstance(sc, dict) and set(sc.keys()) == {"result"}:
            return sc["result"]
        return sc
    text = _text(result).strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return text


def step(n: int, label: str) -> None:
    print(f"\n[{n}] {label}")


async def run(session: ClientSession) -> None:
    # 1. Incident announcement (root of the thread).
    step(1, "Posting incident announcement")
    root_ts = await call(
        session, "send_message", channel=CHANNEL,
        text=(":rotating_light: *Incident Detected*\n"
              "*Pipeline:* `novamart_inventory_sync`\n"
              "*Error:* JSON schema validation error on task `load_inventory`\n"
              "*Time:* 14:03 UTC\n\nInvestigation starting. Updates in this thread."),
    )
    print(f"    root thread ts = {root_ts}")
    await asyncio.sleep(STEP_DELAY)

    # 2. Resolve the data owner.
    step(2, f"Finding data owner: {OWNER!r}")
    matches = await call(session, "find_user", query=OWNER)
    owner = matches[0] if matches else None
    if owner:
        print(f"    found {owner['real_name']} ({owner['id']})")
    else:
        print("    no match — continuing without owner tag/DM")
    await asyncio.sleep(STEP_DELAY)

    # 3 + 4. Tag the owner in-thread and DM them privately.
    if owner:
        step(3, "Tagging owner in the thread")
        await call(session, "send_message", channel=CHANNEL, thread_ts=root_ts,
                   text=(f"<@{owner['id']}> you're the listed owner for "
                         f"*novamart_inventory_sync*. Tagging you for awareness."))
        await asyncio.sleep(STEP_DELAY)

        step(4, "DMing the owner privately")
        await call(session, "send_dm", user=owner["id"],
                   text=("Heads up — novamart_inventory_sync failed and I'm investigating. "
                         "Following up in #" + CHANNEL + "."))
        await asyncio.sleep(STEP_DELAY)

    # 5. Diagnostic findings drip into the thread.
    findings = [
        "Checked the latest DAG run — `load_inventory` failed, upstream tasks succeeded.",
        "Pulled task logs — validation error: unexpected field type on `inventory.json`.",
        "Compared against the catalog contract — `quantity` arrived as string, expected integer.",
    ]
    for i, finding in enumerate(findings, start=1):
        step(5, f"Posting finding {i}/{len(findings)}")
        await call(session, "send_message", channel=CHANNEL, thread_ts=root_ts,
                   text=f":mag: *Finding* — {finding}")
        await asyncio.sleep(STEP_DELAY)

    # 6. HITL approval gate — blocks until a human reacts in Slack.
    step(6, f"HITL approval gate (awaiting a reaction, up to {APPROVAL_TIMEOUT}s)")
    print("    >>> React :white_check_mark: to approve or :x: to cancel in Slack <<<")
    decision = await call(
        session, "request_approval", channel=CHANNEL, thread_ts=root_ts,
        timeout_seconds=APPROVAL_TIMEOUT,
        prompt=("Root cause identified: schema mismatch on `inventory.json` "
                "(`quantity` string vs. expected integer). Create the Jira incident ticket?"),
        _timeout=APPROVAL_TIMEOUT + 30,
    )
    verdict = decision.get("decision")
    print(f"    decision = {verdict}  (by {decision.get('user')})")

    if verdict != "approved":
        await call(session, "send_message", channel=CHANNEL, thread_ts=root_ts,
                   text=(":no_entry: Holding off on the Jira ticket "
                         f"(approval {verdict}). No further action taken."))
        print("\nFlow halted at the gate — exactly the HITL safety behavior.")
        return

    await asyncio.sleep(STEP_DELAY)

    # 7. Final root-cause summary with the Jira link.
    step(7, "Posting root-cause summary")
    await call(session, "send_message", channel=CHANNEL, thread_ts=root_ts,
               text=(":white_check_mark: *Root Cause Identified*\n"
                     "*Cause:* Source emitted `quantity` as a string; loader expects integer.\n"
                     "*Playbook:* attached below.\n"
                     ":jira: *Incident ticket:* "
                     "<https://qbiz.atlassian.net/browse/NOVA-4127|View in Jira>"))
    await asyncio.sleep(STEP_DELAY)

    # 8. Attach the playbook.
    step(8, "Uploading the playbook")
    await call(session, "upload_file", channel=CHANNEL, thread_ts=root_ts,
               filename="novamart_inventory_sync_runbook.md", title="Incident Runbook",
               content=PLAYBOOK, initial_comment="Versioned runbook for this failure mode.")
    await asyncio.sleep(STEP_DELAY)

    # 9. Mark the root message resolved.
    step(9, "Marking the incident resolved")
    await call(session, "add_reaction", channel=CHANNEL, timestamp=root_ts,
               emoji="white_check_mark")
    print("\nIncident resolved — full thread posted in #" + CHANNEL + ".")


async def main() -> int:
    params = StdioServerParameters(
        command="uv", args=["run", "--project", str(MCP_SLACK_DIR), "slack-mcp"],
        env=dict(os.environ), cwd=str(MCP_SLACK_DIR),
    )
    print("Launching Slack MCP server over stdio…")
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            print(f"Connected. {len(tools)} tools: {', '.join(t.name for t in tools)}")
            print("=" * 70)
            await run(session)
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
