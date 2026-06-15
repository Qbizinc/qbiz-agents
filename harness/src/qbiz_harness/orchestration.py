"""Component 6 — Orchestration Controls.

Prevents runaway control flow: infinite loops, unbounded retry chains, and steps that hang.
Also owns **fallback paths** — when a step exhausts its retries, the caller routes to a defined
fallback (a degraded-mode answer, an alternate tool, or escalate-to-human) rather than failing
hard or spinning forever.

Two primitives:
- `with_retry` — a decorator giving an async step bounded retries with exponential backoff and a
  per-call timeout. Per-tool timeouts (a global default is wrong for most tools) are an engineering
  detail settled by passing `timeout=` at the call site.
- `LoopGuard` — a counter that caps how many iterations an agent loop may run before it must
  escalate to a human. This is what stops a reasoning loop that never decides it is done.

Pure enforcement: raises `LoopLimitError` and surfaces the underlying failure; no I/O.
"""

from __future__ import annotations

import asyncio
import functools
from typing import Awaitable, Callable, TypeVar

from qbiz_harness.exceptions import LoopLimitError

T = TypeVar("T")


def with_retry(
    max_attempts: int = 3,
    backoff_base: float = 2.0,
    timeout: float = 30.0,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Wrap an async step with bounded retries, exponential backoff, and a per-call timeout.

    Each attempt is capped at `timeout` seconds. A timed-out or failed attempt is retried up to
    `max_attempts` total; the final failure propagates so the caller can route to a fallback.
    `timeout` is per call site on purpose — a global default is wrong for most tools.
    """

    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(fn)
        async def wrapper(*args: object, **kwargs: object) -> T:
            for attempt in range(max_attempts):
                try:
                    return await asyncio.wait_for(fn(*args, **kwargs), timeout=timeout)
                except (asyncio.TimeoutError, Exception):
                    if attempt == max_attempts - 1:
                        raise
                    await asyncio.sleep(backoff_base ** attempt)
            raise AssertionError("unreachable: retry loop must return or raise")  # pragma: no cover

        return wrapper

    return decorator


class LoopGuard:
    """Caps how many iterations an agent loop may run before it must escalate to a human.

    Call `tick()` once per iteration. The guard raises `LoopLimitError` the moment the cap is
    exceeded, turning an open-ended reasoning loop into a bounded one with a defined exit.
    """

    def __init__(self, max_iterations: int = 10) -> None:
        self._count = 0
        self._max = max_iterations

    def tick(self) -> None:
        self._count += 1
        if self._count > self._max:
            raise LoopLimitError(
                f"Agent exceeded {self._max} iterations — escalating to human"
            )

    @property
    def iterations(self) -> int:
        return self._count
