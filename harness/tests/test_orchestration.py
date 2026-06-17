"""Gate 1 — Component 6 (Orchestration Controls)."""

import asyncio

import pytest

from qbiz_harness import LoopGuard, LoopLimitError, with_retry


def test_loop_guard_allows_up_to_max_then_escalates():
    guard = LoopGuard(max_iterations=3)
    for _ in range(3):
        guard.tick()
    assert guard.iterations == 3
    with pytest.raises(LoopLimitError):
        guard.tick()


async def test_with_retry_returns_on_first_success():
    calls = 0

    @with_retry(max_attempts=3, backoff_base=0.0)
    async def succeed():
        nonlocal calls
        calls += 1
        return "ok"

    assert await succeed() == "ok"
    assert calls == 1


async def test_with_retry_retries_then_succeeds():
    calls = 0

    @with_retry(max_attempts=3, backoff_base=0.0)
    async def flaky():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RuntimeError("transient")
        return "recovered"

    assert await flaky() == "recovered"
    assert calls == 3


async def test_with_retry_propagates_final_failure():
    calls = 0

    @with_retry(max_attempts=2, backoff_base=0.0)
    async def always_fails():
        nonlocal calls
        calls += 1
        raise RuntimeError("permanent")

    with pytest.raises(RuntimeError, match="permanent"):
        await always_fails()
    assert calls == 2  # exhausted both attempts, no more


async def test_with_retry_enforces_per_call_timeout():
    @with_retry(max_attempts=1, backoff_base=0.0, timeout=0.05)
    async def too_slow():
        await asyncio.sleep(1.0)

    with pytest.raises(asyncio.TimeoutError):
        await too_slow()
