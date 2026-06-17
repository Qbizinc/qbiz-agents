"""Gate 1 — Component 8 (Human Checkpoints / HITL).

These verify the *policy* enforcement, not Slack. A fake transport stands in for the Slack MCP's
`request_approval` so the verdict-handling and timeout-policy logic is tested in isolation.
"""

import pytest

from qbiz_harness import (
    ApprovalDecision,
    ApprovalTransport,
    HitlEscalationRequired,
    TimeoutPolicy,
    hitl_checkpoint,
)


class FakeTransport:
    """Stands in for the Slack MCP `request_approval` tool. Returns a canned verdict and records
    the call so tests can assert the prompt/channel were passed through."""

    def __init__(self, result: dict):
        self._result = result
        self.calls: list[dict] = []

    async def request_approval(self, *, channel, prompt, timeout_seconds, thread_ts=None):
        self.calls.append(
            {
                "channel": channel,
                "prompt": prompt,
                "timeout_seconds": timeout_seconds,
                "thread_ts": thread_ts,
            }
        )
        return self._result


def _checkpoint(result, **kwargs):
    transport = FakeTransport(result)
    return transport, hitl_checkpoint(transport, channel="C123", prompt="Proceed?", **kwargs)


async def test_fake_transport_satisfies_protocol():
    # The protocol is runtime-checkable, so the fake genuinely matches the surface we depend on.
    assert isinstance(FakeTransport({"decision": "approved"}), ApprovalTransport)


async def test_approved_proceeds():
    transport, coro = _checkpoint({"decision": "approved", "user": "U1", "reaction": "white_check_mark"})
    result = await coro
    assert isinstance(result, ApprovalDecision)
    assert result.approved is True
    assert bool(result) is True
    assert result.decision == "approved"
    assert result.user == "U1"
    assert result.timed_out is False
    assert result.raw["reaction"] == "white_check_mark"  # extra keys preserved for audit


async def test_rejected_halts_regardless_of_policy():
    # A human rejection is honoured even under the most permissive timeout policy.
    _, coro = _checkpoint({"decision": "rejected", "user": "U2"}, timeout_policy=TimeoutPolicy.FAIL_OPEN)
    result = await coro
    assert result.approved is False
    assert result.decision == "rejected"
    assert result.user == "U2"
    assert result.timed_out is False


async def test_timeout_fail_closed_does_not_proceed():
    _, coro = _checkpoint({"decision": "timed_out", "user": None}, timeout_policy=TimeoutPolicy.FAIL_CLOSED)
    result = await coro
    assert result.approved is False
    assert result.timed_out is True
    assert result.decision == "timed_out"


async def test_fail_closed_is_the_default():
    # No timeout_policy passed → the HIGH+ safe default applies.
    _, coro = _checkpoint({"decision": "timed_out"})
    result = await coro
    assert result.policy is TimeoutPolicy.FAIL_CLOSED
    assert result.approved is False


async def test_timeout_fail_open_proceeds():
    _, coro = _checkpoint({"decision": "timed_out"}, timeout_policy=TimeoutPolicy.FAIL_OPEN)
    result = await coro
    assert result.approved is True
    assert result.timed_out is True


async def test_timeout_escalate_raises():
    _, coro = _checkpoint({"decision": "timed_out"}, timeout_policy=TimeoutPolicy.ESCALATE)
    with pytest.raises(HitlEscalationRequired):
        await coro


async def test_unrecognised_verdict_treated_as_timeout():
    # A malformed transport response must never silently approve under fail-closed.
    _, coro = _checkpoint({"decision": "garbage"}, timeout_policy=TimeoutPolicy.FAIL_CLOSED)
    result = await coro
    assert result.approved is False
    assert result.timed_out is True


async def test_missing_decision_treated_as_timeout():
    _, coro = _checkpoint({}, timeout_policy=TimeoutPolicy.FAIL_CLOSED)
    result = await coro
    assert result.approved is False
    assert result.timed_out is True


async def test_prompt_and_thread_passed_through():
    transport = FakeTransport({"decision": "approved"})
    await hitl_checkpoint(
        transport,
        channel="C9",
        prompt="Create Jira incident?",
        timeout_seconds=45,
        thread_ts="1700000000.001",
    )
    assert transport.calls == [
        {
            "channel": "C9",
            "prompt": "Create Jira incident?",
            "timeout_seconds": 45,
            "thread_ts": "1700000000.001",
        }
    ]
