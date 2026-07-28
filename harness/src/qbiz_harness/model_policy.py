"""Component 5 extension — Model-Tier Policy.

Model choice is the single biggest cost-and-capability lever an agent has, so the harness
governs it the way it governs spend and action counts: **enforce a bound in code, don't let the
model reason its way past it.** ("Instructions are a request; the harness is enforcement" — a
step *told* to use a weak model can decide otherwise; a tier cap cannot be reasoned around.)

**Enforce, not route.** The launcher/orchestrator still *picks* which model runs a step —
routing is reasoning-adjacent and stays out of the harness. The harness *caps* that choice: each
activity declares an allowed tier band, and a call requesting a model outside the band is
rejected *before* the API call, exactly as `CostGovernor.pre_call` rejects an over-budget call.

Tiers are provider-agnostic ordinals (`WEAK < MID < FRONTIER`); concrete model strings map to a
tier via caller-supplied config, never hardcoded here — the same band works whether the caller
runs Claude, Gemini, or both.

This module is pure enforcement: it raises `ModelPolicyError` and holds no I/O. The call site
catches the rejection and records it through the audit log, same as every other component.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from qbiz_harness.exceptions import ModelPolicyError


class Tier(IntEnum):
    """Provider-agnostic model-strength ordinal."""

    WEAK = 1
    MID = 2
    FRONTIER = 3


@dataclass(frozen=True, slots=True)
class ActivityBand:
    """The allowed model-tier range for one activity.

    - `max_tier` — the hard **ceiling**, always enforced. Cost / blast-radius: the ironclad
      guarantee that a trivial step can never burn a frontier model.
    - `min_tier` / `floor_hard` — the **floor**. Quality is a judgment, not a safety boundary,
      so by default `min_tier` is only a template default (not enforced); set `floor_hard=True`
      for the rare activity where under-tiering is itself a risk worth hard-rejecting. The real
      quality backstop is the evaluator (Component 7).
    - `requires_multi_model` — this activity's output is checked by a *different* model than the
      one that produced it (Component 7's evaluator rule). `ModelPolicy` validates at
      construction time that a band making this claim actually admits more than one concrete
      model — otherwise the evaluator rule can never be satisfied, which is a config bug, not
      something that should surface as a confusing runtime failure later. Validated only —
      `check()` does not yet enforce that the evaluator's model differs from the primary's;
      that lands with Component 7.
    """

    max_tier: Tier
    min_tier: Tier = Tier.WEAK
    floor_hard: bool = False
    requires_multi_model: bool = False

    def __post_init__(self) -> None:
        if self.min_tier > self.max_tier:
            raise ModelPolicyError(
                f"invalid band: min_tier={self.min_tier.name} exceeds max_tier={self.max_tier.name}"
            )


class ModelPolicy:
    """Caps the model tier per activity.

    Policy comes only from construction-time config — a `tier_map` (concrete model string ->
    `Tier`) and `activities` (activity name -> `ActivityBand`) — never from LLM output, so no
    amount of model reasoning can widen it. Both are defensively copied at construction, so
    mutating the caller's original dicts afterward has no effect on an already-built policy.

    Mirrors `CostGovernor.pre_call`: the check fires before the API call it guards, so a
    rejected request never actually reaches the model.
    """

    def __init__(
        self,
        tier_map: dict[str, Tier],
        activities: dict[str, ActivityBand],
    ) -> None:
        try:
            self._tier_of = {model: Tier(tier) for model, tier in tier_map.items()}
        except ValueError as exc:
            raise ModelPolicyError(f"invalid tier_map entry: {exc}") from exc
        self._bands = dict(activities)
        self._validate_evaluator_bands()

    def _validate_evaluator_bands(self) -> None:
        """Config-time check: an activity marked `requires_multi_model` must admit more than one
        concrete model within its band, or the evaluator-different-model rule can never be
        satisfied. Raises here — at policy construction — rather than letting it fail confusingly
        the first time an evaluator run can't find a second model to use."""
        for activity, band in self._bands.items():
            if not band.requires_multi_model:
                continue
            admitted = [
                model
                for model, tier in self._tier_of.items()
                if tier <= band.max_tier and (not band.floor_hard or tier >= band.min_tier)
            ]
            if len(admitted) < 2:
                raise ModelPolicyError(
                    f"activity {activity!r} requires a different-model evaluator, but its band "
                    f"(min={band.min_tier.name}, max={band.max_tier.name}) admits only "
                    f"{len(admitted)} mapped model(s): {admitted}"
                )

    def check(self, activity: str, model: str) -> None:
        """Raise `ModelPolicyError` if `model` is not allowed to run `activity`.

        `activity` must be a structural label the orchestrator supplies (which node in the DAG
        is running) — never parsed from model output, same principle as `agent_id` in
        Component 3. `model` is the only value the caller/router actually chooses; it is
        precisely what this check exists to bound.
        """
        tier = self._tier_of.get(model)
        if tier is None:
            raise ModelPolicyError(f"Model {model!r} is not tier-mapped; refusing (ungoverned)")
        band = self._bands.get(activity)
        if band is None:
            raise ModelPolicyError(f"No model band for activity {activity!r}; refusing")
        if tier > band.max_tier:
            raise ModelPolicyError(
                f"{activity!r} permits at most {band.max_tier.name}; {model!r} is {tier.name}"
            )
        if band.floor_hard and tier < band.min_tier:
            raise ModelPolicyError(
                f"{activity!r} requires at least {band.min_tier.name}; {model!r} is {tier.name}"
            )
