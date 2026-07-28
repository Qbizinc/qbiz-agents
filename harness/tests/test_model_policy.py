"""Gate 1 — Component 5 extension (Model-Tier Policy).

Covers the checks-and-balances list from HARNESS_PLAN.md's Gate 1 section: hard ceiling, hard
vs. soft floor, cross-provider parity, fail-closed on the unknown, policy not LLM-widenable,
the evaluator different-model config validation, and the recommended call-site order + audit
pattern.
"""

import pytest

from qbiz_harness import (
    ActivityBand,
    AuditLog,
    CostGovernor,
    ModelPolicy,
    ModelPolicyError,
    Tier,
)
from qbiz_harness.exceptions import HarnessError

_TIER_MAP = {
    "claude-haiku-4": Tier.WEAK,
    "gemini-flash-2": Tier.WEAK,
    "claude-sonnet-5": Tier.MID,
    "gemini-pro-2": Tier.MID,
    "claude-opus-5": Tier.FRONTIER,
    "gemini-ultra-2": Tier.FRONTIER,
}


def _policy(**activities: ActivityBand) -> ModelPolicy:
    return ModelPolicy(tier_map=_TIER_MAP, activities=activities)


# --- ceiling: hard, always enforced --------------------------------------------------------


def test_ceiling_allows_model_at_or_below_max_tier():
    policy = _policy(file_ticket=ActivityBand(max_tier=Tier.WEAK))
    policy.check("file_ticket", "claude-haiku-4")  # WEAK <= WEAK — no raise


def test_ceiling_blocks_model_above_max_tier():
    policy = _policy(file_ticket=ActivityBand(max_tier=Tier.WEAK))
    with pytest.raises(ModelPolicyError):
        policy.check("file_ticket", "claude-opus-5")  # FRONTIER > WEAK


# --- floor: hard only when floor_hard=True ---------------------------------------------------


def test_soft_floor_does_not_block_a_below_floor_model():
    policy = _policy(
        investigate=ActivityBand(max_tier=Tier.FRONTIER, min_tier=Tier.MID, floor_hard=False)
    )
    policy.check("investigate", "claude-haiku-4")  # below MID, but floor is soft — no raise


def test_hard_floor_blocks_a_below_floor_model():
    policy = _policy(
        investigate=ActivityBand(max_tier=Tier.FRONTIER, min_tier=Tier.MID, floor_hard=True)
    )
    with pytest.raises(ModelPolicyError):
        policy.check("investigate", "claude-haiku-4")  # below MID, hard floor


def test_hard_floor_allows_model_at_or_above_floor():
    policy = _policy(
        investigate=ActivityBand(max_tier=Tier.FRONTIER, min_tier=Tier.MID, floor_hard=True)
    )
    policy.check("investigate", "claude-sonnet-5")  # MID — at the floor, allowed


# --- cross-provider parity -------------------------------------------------------------------


def test_cross_provider_parity_same_tier_both_admitted():
    policy = _policy(file_ticket=ActivityBand(max_tier=Tier.WEAK))
    policy.check("file_ticket", "claude-haiku-4")  # Claude WEAK
    policy.check("file_ticket", "gemini-flash-2")  # Gemini WEAK — same band, both pass


def test_cross_provider_parity_both_providers_frontier_rejected():
    policy = _policy(mid_step=ActivityBand(max_tier=Tier.MID))
    with pytest.raises(ModelPolicyError):
        policy.check("mid_step", "claude-opus-5")  # Claude frontier — over the MID ceiling
    with pytest.raises(ModelPolicyError):
        policy.check("mid_step", "gemini-ultra-2")  # Gemini frontier — same ceiling, same result


# --- fail-closed on the unknown -----------------------------------------------------------


def test_fail_closed_on_unmapped_model():
    policy = _policy(file_ticket=ActivityBand(max_tier=Tier.WEAK))
    with pytest.raises(ModelPolicyError):
        policy.check("file_ticket", "some-new-model-nobody-mapped-yet")


def test_fail_closed_on_unmapped_activity():
    policy = _policy(file_ticket=ActivityBand(max_tier=Tier.WEAK))
    with pytest.raises(ModelPolicyError):
        policy.check("some_activity_never_configured", "claude-haiku-4")


# --- policy is not LLM-widenable ------------------------------------------------------------


def test_mutating_caller_dicts_after_construction_does_not_affect_policy():
    tier_map = dict(_TIER_MAP)
    activities = {"file_ticket": ActivityBand(max_tier=Tier.WEAK)}
    policy = ModelPolicy(tier_map=tier_map, activities=activities)

    # Mutate the caller's own dicts after the policy is built.
    tier_map["claude-opus-5"] = Tier.WEAK  # pretend to "downgrade" frontier to weak
    activities["file_ticket"] = ActivityBand(max_tier=Tier.FRONTIER)  # pretend to widen the band

    # The policy's internal state must be unaffected — it only reads its own defensive copies.
    with pytest.raises(ModelPolicyError):
        policy.check("file_ticket", "claude-opus-5")


def test_model_policy_exposes_no_public_mutator():
    """The only way to change what a ModelPolicy allows is to construct a new one — there is no
    setter a caller (or a model, indirectly) could invoke at runtime to widen the ceiling. An
    allowlist, not equality with a fixed list: a future read-only accessor (e.g.
    `allowed_models(activity)` for the downgrade-retry path) is a one-line addition here, but
    anything else appearing on an enforcement primitive's public surface should fail loudly and
    put a human in the loop."""
    KNOWN_READ_ONLY = {"check"}  # add here deliberately, with a note on why it's read-only
    policy = _policy(file_ticket=ActivityBand(max_tier=Tier.WEAK))
    public_attrs = {a for a in dir(policy) if not a.startswith("_")}
    assert public_attrs <= KNOWN_READ_ONLY


# --- evaluator different-model rule stays satisfiable ----------------------------------------


def test_construction_fails_when_evaluator_band_admits_only_one_model():
    single_model_map = {"claude-opus-5": Tier.FRONTIER}  # deliberately only one mapped model
    with pytest.raises(ModelPolicyError):
        ModelPolicy(
            tier_map=single_model_map,
            activities={
                "review": ActivityBand(
                    max_tier=Tier.FRONTIER,
                    min_tier=Tier.FRONTIER,
                    floor_hard=True,
                    requires_multi_model=True,
                )
            },
        )  # only one model is mapped at all — it can't evaluate itself differently


def test_construction_succeeds_when_evaluator_band_admits_two_or_more_models():
    policy = _policy(
        review=ActivityBand(max_tier=Tier.MID, requires_multi_model=True)
    )  # claude-sonnet-5 and gemini-pro-2 both fit MID
    policy.check("review", "claude-sonnet-5")


# --- ModelPolicyError is part of the HarnessError boundary -------------------------------------


def test_model_policy_error_is_a_harness_error():
    """The entire point of the leaf: a caller can `except HarnessError` once and still catch a
    model-tier rejection, so the call-site boundary and audit stamping both work unmodified."""
    assert issubclass(ModelPolicyError, HarnessError)


# --- construction-time validation beyond the evaluator rule -------------------------------------


def test_construction_fails_when_min_tier_exceeds_max_tier():
    """An inverted band would otherwise construct cleanly and reject every model at runtime —
    half by the ceiling, half by the floor. Caught at construction instead."""
    with pytest.raises(ModelPolicyError):
        ActivityBand(max_tier=Tier.WEAK, min_tier=Tier.FRONTIER, floor_hard=True)


def test_construction_fails_on_non_tier_value_in_tier_map():
    """A raw int (e.g. from YAML config per [D8]) must be coerced/rejected at construction, not
    survive ordinal comparisons and die later on `tier.name` with a bare AttributeError that
    escapes the HarnessError boundary and skips audit stamping."""
    with pytest.raises(ModelPolicyError):
        ModelPolicy(
            tier_map={"weird-model": 99},
            activities={"file_ticket": ActivityBand(max_tier=Tier.WEAK)},
        )


def test_evaluator_band_validation_mirrors_soft_floor_at_check_time():
    """A soft floor (`floor_hard=False`) admits models below `min_tier` at `check()` time, so the
    construction-time evaluator-admission count must count them too — otherwise a satisfiable
    config is rejected as if the floor were hard."""
    tier_map = {"claude-sonnet-5": Tier.MID, "claude-opus-5": Tier.FRONTIER}
    # Soft floor: MID is below min_tier but admitted at check() time, so two models qualify.
    policy = ModelPolicy(
        tier_map=tier_map,
        activities={
            "review": ActivityBand(
                max_tier=Tier.FRONTIER,
                min_tier=Tier.FRONTIER,
                floor_hard=False,
                requires_multi_model=True,
            )
        },
    )
    policy.check("review", "claude-sonnet-5")  # below min_tier, but floor is soft — no raise


# --- call-site order + audit (reference wiring) -----------------------------------------------


def test_reference_wiring_order_and_single_audit_intervention_on_rejection():
    """The recommended call-site order: model_policy.check() before cost_governor.pre_call() —
    a rejected tier never reaches the token estimator — and exactly one harness_intervention
    audit event on a rejection, none on an allowed call."""
    policy = _policy(file_ticket=ActivityBand(max_tier=Tier.WEAK))
    governor = CostGovernor(token_limit=1000, spend_limit_usd=1.0)
    audit = AuditLog()

    def run_step(activity: str, model: str) -> None:
        try:
            policy.check(activity, model)
            governor.pre_call(estimated_tokens=100)
            governor.post_call(tokens_used=100, cost_usd=0.01)  # simulate the completed call
        except ModelPolicyError as exc:
            audit.record_intervention(
                agent_id="test-agent",
                action=f"call:{activity}",
                component="model_policy",
                prevented=str(exc),
            )
            return
        audit.record(
            agent_id="test-agent",
            action=f"call:{activity}",
            decision="allowed",
        )

    # Allowed call: no intervention recorded, and the token estimator was reached.
    run_step("file_ticket", "claude-haiku-4")
    assert governor.tokens_used == 100
    assert len(audit.events) == 1
    assert audit.events[0].decision == "allowed"

    # Rejected call: exactly one intervention, and the token estimator was never reached
    # (tokens_used unchanged from the prior allowed call).
    run_step("file_ticket", "claude-opus-5")
    assert governor.tokens_used == 100  # unchanged — pre_call never ran
    assert len(audit.events) == 2
    assert audit.events[1].intervention is not None
    assert audit.events[1].intervention.component == "model_policy"


def test_reference_wiring_activity_is_structural_not_model_derived():
    """`activity` must come from the orchestrator (which DAG node is running), never from
    parsing the model's own output — the same principle as `agent_id` elsewhere in the harness.
    Simulate a model response that tries to smuggle a different activity label; the reference
    wiring only ever keys off the orchestrator-supplied `activity` argument, so the smuggled
    value has no effect on which band is enforced."""
    policy = _policy(
        file_ticket=ActivityBand(max_tier=Tier.WEAK),
        deploy=ActivityBand(max_tier=Tier.FRONTIER),
    )

    def run_step(activity: str, model: str, model_output: dict) -> None:
        # `check` is called with the orchestrator's `activity` argument; `model_output` (what a
        # model might claim about its own step) is never consulted for it.
        policy.check(activity, model)

    # Orchestrator says this step is the tightly-banded "file_ticket", regardless of what the
    # model's own output claims about itself.
    with pytest.raises(ModelPolicyError):
        run_step(
            "file_ticket",
            "claude-opus-5",
            model_output={"activity": "deploy"},  # smuggled — must not widen the effective band
        )
