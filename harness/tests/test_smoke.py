"""Smoke tests — the package imports and its exception contract holds.

This is the seed of Gate 1. As components land, their unit tests join this directory.
"""

import qbiz_harness
from qbiz_harness.exceptions import (
    BudgetExceededError,
    HarnessError,
    InputRejectedError,
    LoopLimitError,
    OutputRejectedError,
    PermissionDeniedError,
    RateLimitError,
)


def test_package_has_version():
    assert qbiz_harness.__version__ == "0.1.0"


def test_every_harness_error_subclasses_the_base():
    for exc in (
        InputRejectedError,
        OutputRejectedError,
        RateLimitError,
        BudgetExceededError,
        LoopLimitError,
        PermissionDeniedError,
    ):
        assert issubclass(exc, HarnessError)


def test_base_is_an_exception():
    assert issubclass(HarnessError, Exception)
