#!/usr/bin/env python3
"""Harness demo — watch the harness stop a runaway agent, in code.

This is a *no-LLM* demo. It deliberately needs no API key (the LLM-provider decision `[D3]` is
still open), which the plan explicitly allows for the demo: it shows the harness *mechanics*
without the live-LLM loop.

The scenario is the plan's HIGH-tier reference agent — the **Agentic Incident DAG**. Its job:
investigate a production incident, post one notification to the on-call channel, and (if needed)
file a ticket. Because it writes to Slack and creates tickets, it runs inside a harness:

    - Component 5 (CostGovernor): caps messages sent, tokens, spend; carries a kill switch.
    - Component 6 (LoopGuard):    caps how many reasoning iterations the loop may run.
    - Audit Log:                  records every action and the harness's verdict.

We script the agent to misbehave — the way a real reasoning loop or a prompt injection would —
and let the harness do its job. The point the team should take away:

    "Instructions are a request. The harness is enforcement."

Run it:
    uv run python demo/incident_runaway.py
    # or, without installing:  python demo/incident_runaway.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Windows consoles default to cp1252 and choke on the box-drawing / emoji glyphs below.
# Force UTF-8 so the demo renders the same everywhere.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

# Let the demo run straight from the repo without an install step.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qbiz_harness import AuditLog, CostGovernor, HarnessError, LoopGuard  # noqa: E402

AGENT_ID = "incident-agent"
ONCALL_CHANNEL = "qbiz_slackbot_testing"  # the designated test channel


# --- tiny terminal styling (dependency-free; respects NO_COLOR and non-tty) -------------------

_USE_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def bold(t: str) -> str:
    return _c("1", t)


def green(t: str) -> str:
    return _c("32", t)


def red(t: str) -> str:
    return _c("31", t)


def yellow(t: str) -> str:
    return _c("33", t)


def dim(t: str) -> str:
    return _c("2", t)


def scene(title: str) -> None:
    print("\n" + bold("━" * 70))
    print(bold(title))
    print(bold("━" * 70))


def allowed(msg: str) -> None:
    print(f"  {green('✓ ALLOWED')}  {msg}")


def denied(msg: str) -> None:
    print(f"  {red('✗ BLOCKED')}  {msg}")


def agent_says(msg: str) -> None:
    print(f"  {dim('agent ▸')} {dim(msg)}")


# --- the simulated agent's only consequential action ------------------------------------------
#
# In the real DAG this would call the Slack MCP's send_message. Here it is a stub — the harness
# does not care what the action *does*, only that it is gated before it runs.


def _do_send_message(channel: str, text: str) -> None:
    """Stand-in for the Slack MCP send_message tool. No real I/O in the demo."""
    _ = (channel, text)


def attempt_send(gov: CostGovernor, audit: AuditLog, channel: str, text: str) -> bool:
    """Try to send one Slack message *through the harness*. Returns whether it went out.

    The order matters: the governor is asked for permission BEFORE the send runs, so the cap
    bounds what actually happens — not just what gets billed afterward.
    """
    try:
        gov.record_action("messages_sent")  # harness check, in code
        _do_send_message(channel, text)
        audit.record(agent_id=AGENT_ID, action="send_message", decision="allowed",
                     inputs={"channel": channel, "text": text})
        allowed(f'posted to #{channel}: "{text}"')
        return True
    except HarnessError as exc:
        audit.record(agent_id=AGENT_ID, action="send_message", decision="denied",
                     inputs={"channel": channel, "text": text}, reason=str(exc))
        denied(f"send refused — {exc}")
        return False


# --- the run ----------------------------------------------------------------------------------


def run_demo() -> None:
    audit_path = Path(__file__).resolve().parent / "audit_trail.jsonl"
    if audit_path.exists():
        audit_path.unlink()  # fresh trail each run
    audit = AuditLog(path=audit_path)

    # The harness this HIGH-tier agent runs inside. Limits are deliberately small so the demo
    # is short; in production they come from the agent's limits.yaml.
    gov = CostGovernor(
        token_limit=50_000,
        spend_limit_usd=0.50,
        action_limits={"messages_sent": 3},  # at most 3 Slack messages this run
    )
    loop_guard = LoopGuard(max_iterations=5)

    print(bold("\nAgentic Incident DAG — harnessed run"))
    print(dim("HIGH-tier agent: writes to Slack, files tickets. Wrapped in Components 5 + 6 + audit."))
    print(dim(f"Caps this run: messages_sent ≤ 3, loop ≤ 5 iterations, spend ≤ $0.50"))

    # ----------------------------------------------------------------------------------------
    scene("Scene 1 — Normal operation")
    agent_says("New incident INC-4471. Investigating, then notifying on-call.")
    attempt_send(gov, audit, ONCALL_CHANNEL,
                 "🚨 INC-4471: checkout latency spiking. Investigating. — incident-agent")

    # ----------------------------------------------------------------------------------------
    scene("Scene 2 — The reasoning loop goes wrong")
    print(dim("  The agent's instructions said 'notify on-call.' Its reasoning loops and it"))
    print(dim("  starts re-sending the same alert. This is exactly the cheap-but-destructive"))
    print(dim("  failure a spend cap would NOT catch — each message is nearly free."))
    print()
    sent_in_loop = 0
    for i in range(10):  # the agent WANTS to send 10 more
        try:
            loop_guard.tick()
        except HarnessError as exc:
            audit.record(agent_id=AGENT_ID, action="loop_iteration", decision="denied",
                         reason=str(exc))
            denied(f"loop halted — {exc}")
            break
        agent_says(f"(iteration {loop_guard.iterations}) re-sending alert, just in case…")
        if attempt_send(gov, audit, ONCALL_CHANNEL, f"🚨 INC-4471 reminder #{i + 1}"):
            sent_in_loop += 1

    print()
    print(f"  {yellow('→')} The agent tried to send 10 more. The harness let "
          f"{green(str(sent_in_loop))} through, then capped the blast radius — in code.")

    # ----------------------------------------------------------------------------------------
    scene("Scene 3 — Operator pulls the kill switch")
    agent_says("Still looping. Now wants to escalate by filing 50 Jira tickets.")
    print(dim("  An operator watching the channel engages the global kill switch."))
    gov.kill()
    audit.record(agent_id=AGENT_ID, action="kill_switch", decision="engaged", user="operator")
    print(f"  {red('⏻ KILL SWITCH ENGAGED')} by operator")
    # The agent does not know it has been killed; it keeps trying. Every guarded call now fails.
    try:
        gov.record_action("tickets_created")
    except HarnessError as exc:
        audit.record(agent_id=AGENT_ID, action="create_ticket", decision="denied", reason=str(exc))
        denied(f"ticket creation refused — {exc}")

    # ----------------------------------------------------------------------------------------
    _print_audit_summary(audit)


def _print_audit_summary(audit: AuditLog) -> None:
    scene("Audit trail — forensic reconstruction of the whole run")
    print(dim(f"  Every action and the harness verdict, append-only. Persisted to:"))
    print(dim(f"  demo/audit_trail.jsonl\n"))

    for event in audit.events:
        verdict = event.decision
        if verdict == "allowed":
            tag = green(f"{verdict:<8}")
        elif verdict == "engaged":
            tag = red(f"{verdict:<8}")
        else:
            tag = red(f"{verdict:<8}")
        line = f"  {dim(event.ts[11:19])}  {tag}  {event.action}"
        if event.reason:
            line += dim(f"   ({event.reason})")
        print(line)

    total = len(audit.events)
    blocked = len(audit.by_decision("denied"))
    print()
    print(bold(f"  {total} actions recorded · {blocked} blocked by the harness."))
    print(bold("  Instructions are a request. The harness is enforcement."))
    print()


if __name__ == "__main__":
    run_demo()
