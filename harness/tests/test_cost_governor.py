"""Gate 1 — Component 5 (Cost & Compute Governors).

These tests assert the governor *fires at the configured threshold* — the plan's Gate 1 line
"test that cost/token governors fire at the configured threshold."
"""

import pytest

from qbiz_harness import BudgetExceededError, CostGovernor


def _governor(**overrides) -> CostGovernor:
    defaults = dict(token_limit=1000, spend_limit_usd=1.00, action_limits={"messages_sent": 3})
    defaults.update(overrides)
    return CostGovernor(**defaults)


def test_pre_call_allows_within_token_budget():
    gov = _governor()
    gov.pre_call(estimated_tokens=500)  # under 1000 — no raise


def test_pre_call_blocks_over_token_budget():
    gov = _governor()
    with pytest.raises(BudgetExceededError):
        gov.pre_call(estimated_tokens=1001)


def test_post_call_blocks_when_spend_cap_exceeded():
    gov = _governor()
    with pytest.raises(BudgetExceededError):
        gov.post_call(tokens_used=10, cost_usd=1.50)
    assert gov.spend_usd == pytest.approx(1.50)  # usage is recorded even on the breach


def test_action_limit_allows_up_to_cap_then_blocks():
    gov = _governor()
    for _ in range(3):
        gov.record_action("messages_sent")  # 3 allowed
    with pytest.raises(BudgetExceededError):
        gov.record_action("messages_sent")  # 4th is over the cap


def test_unlimited_action_kind_never_blocks():
    gov = _governor()
    for _ in range(100):
        gov.record_action("reads")  # no limit configured for "reads"
    assert gov.action_counts["reads"] == 100


def test_kill_switch_halts_all_guarded_calls():
    gov = _governor()
    gov.kill()
    assert gov.killed
    with pytest.raises(BudgetExceededError):
        gov.pre_call(estimated_tokens=1)
    with pytest.raises(BudgetExceededError):
        gov.record_action("messages_sent")


def test_redundancy_detection_refuses_repeated_work():
    gov = _governor()
    gov.guard_redundant("incident-42:notify")  # first time is fine
    with pytest.raises(BudgetExceededError):
        gov.guard_redundant("incident-42:notify")  # second time refused
