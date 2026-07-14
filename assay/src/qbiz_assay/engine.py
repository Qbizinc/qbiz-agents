"""Assessment engine — runs collectors and narration under the harness.

The engine is the harness *call site*: the enforcement components stay pure (raise, no I/O)
and the engine catches their rejections and records them through the audit log, exactly as
`qbiz_harness` prescribes. The design is deterministic-first: collectors are free (pure
parsing, zero tokens); the narrator is the only metered stage. If the governor cuts the
narrator off mid-run, the engine degrades to the rule-based narrator for the remaining
sections — a governed assessment always completes, it never half-fails.

The engine is generic machinery: which dimensions exist, their titles and weights, and the
score bands all come from the ``AssessmentConfig`` registry it is handed — it iterates that
registry and the scores derived from it, never a compiled-in list.

This makes Assay the meta-demo: the report we hand a prospect was produced by an agent running
under the same harness we sell, and the report's final section says so with numbers.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable, Sequence
from uuid import uuid4

from qbiz_harness import (
    AuditLog,
    BudgetExceededError,
    CostGovernor,
    LoopGuard,
    LoopLimitError,
)

from qbiz_assay.assessor import Narrator, RuleBasedNarrator
from qbiz_assay.collectors import CollectorResult
from qbiz_assay.config import AssessmentConfig, baseline_config
from qbiz_assay.findings import SEVERITY_ORDER, DimensionId, Finding, Severity
from qbiz_assay.rubric import DimensionScore, overall_score, score_dimensions

AGENT_ID = "assay-agent"
COHORT = "assay"

#: A named, ready-to-run collector: the name keys the redundancy guard and the audit trail.
CollectorSpec = tuple[str, Callable[[], CollectorResult]]


@dataclass(slots=True)
class AssessmentLimits:
    """Hard caps for one assessment run. Deliberately generous defaults — the point is that
    caps *exist*, not that they pinch; a demo or a paranoid caller tightens them."""

    token_limit: int = 60_000
    spend_limit_usd: float = 2.00
    max_iterations: int = 24
    max_narrative_sections: int = 10


@dataclass(slots=True)
class Assessment:
    """Everything one run produced, including the config that shaped it and the governor and
    audit log that governed it."""

    client_name: str
    run_id: str
    collector_results: list[CollectorResult]
    findings: list[Finding]
    scores: dict[DimensionId, DimensionScore]
    overall: int | None
    narratives: dict[str, str]
    config: AssessmentConfig
    fallback_sections: list[str] = field(default_factory=list)
    audit: AuditLog = field(default_factory=AuditLog)
    governor: CostGovernor | None = None
    limits: AssessmentLimits = field(default_factory=AssessmentLimits)


def _estimate_tokens(context: dict[str, object]) -> int:
    """Crude pre-call estimate: prompt scaffolding plus the serialized context."""
    return 300 + len(json.dumps(context, default=str)) // 4


def _section_context(
    section: str,
    client_name: str,
    scores: dict[DimensionId, DimensionScore],
    overall: int | None,
    overall_band: str,
    config: AssessmentConfig,
) -> dict[str, object]:
    """The narrator's entire world for one section — it explains this, nothing else."""
    if section == "executive_summary":
        findings = [f for s in scores.values() for f in s.findings]
        return {
            "client_name": client_name,
            "overall": overall,
            "band": overall_band,
            "dimensions": [
                {
                    "title": config.rubric.title_for(dim),
                    "score": score.score,
                    "band": score.band,
                    "finding_count": len(score.findings),
                }
                for dim, score in scores.items()
            ],
            "finding_count": len(findings),
            "critical_count": sum(1 for f in findings if f.severity == Severity.CRITICAL),
        }

    score = scores[section]
    ordered = sorted(score.findings, key=lambda f: SEVERITY_ORDER[f.severity])
    return {
        "title": config.rubric.title_for(section),
        "score": score.score,
        "band": score.band,
        "findings": [
            {
                "severity": f.severity.value,
                "title": f.title,
                "remediation": f.remediation,
            }
            for f in ordered[:5]
        ],
    }


def run_assessment(
    *,
    client_name: str,
    collectors: Sequence[CollectorSpec],
    narrator: Narrator | None = None,
    audit: AuditLog | None = None,
    limits: AssessmentLimits | None = None,
    config: AssessmentConfig | None = None,
) -> Assessment:
    """Run one governed assessment: collect (free) → score (free) → narrate (metered).

    ``config`` defaults to the shipped Qbiz baseline; an engagement profile supplies an
    overridden one (see ``qbiz_assay.profile``).

    Harness wiring, per component:
    - **CostGovernor** — token/spend caps on the narrator; an action cap on narrative
      sections; the redundancy guard refuses re-collecting an artifact within one run.
    - **LoopGuard** — bounds total engine iterations, so no stage can spin.
    - **AuditLog** — every collection, narration, and intervention lands in the trail,
      tagged with a per-run ``incident_id`` and the ``assay`` cohort.
    """
    limits = limits or AssessmentLimits()
    audit = audit or AuditLog()
    config = config or baseline_config()
    active: Narrator = narrator or RuleBasedNarrator()
    fallback = RuleBasedNarrator()

    run_id = uuid4().hex[:12]
    job_id = re.sub(r"[^a-z0-9]+", "-", client_name.lower()).strip("-") or "client"
    tags: dict[str, object] = {
        "agent_id": AGENT_ID,
        "incident_id": run_id,
        "cohort": COHORT,
        "job_id": job_id,
    }

    governor = CostGovernor(
        token_limit=limits.token_limit,
        spend_limit_usd=limits.spend_limit_usd,
        action_limits={"narrative_sections": limits.max_narrative_sections},
    )
    guard = LoopGuard(max_iterations=limits.max_iterations)

    # --- Stage 1: deterministic collection (zero tokens) ---------------------------------
    results: list[CollectorResult] = []
    for name, run in collectors:
        try:
            guard.tick()
        except LoopLimitError as exc:
            audit.record_intervention(
                action=f"collect:{name}",
                component="loop_guard",
                prevented=str(exc),
                reason="loop cap reached during collection; skipping remaining collectors",
                **tags,
            )
            break
        try:
            governor.guard_redundant(f"collect:{name}")
        except BudgetExceededError as exc:
            audit.record_intervention(
                action=f"collect:{name}",
                component="cost_governor",
                prevented=str(exc),
                **tags,
            )
            continue
        result = run()
        results.append(result)
        audit.record(
            action=f"collect:{name}",
            decision="allowed",
            outputs=dict(result.stats),
            **tags,
        )

    # --- Stage 2: deterministic scoring ---------------------------------------------------
    findings = [f for r in results for f in r.findings]
    assessed: set[DimensionId] = set()
    for r in results:
        assessed |= r.dimensions
    scores = score_dimensions(findings, assessed, config.rubric)
    overall = overall_score(scores, config.rubric)
    overall_band = config.rubric.band_for(overall) if overall is not None else "Not assessed"

    # --- Stage 3: narration, metered by the governor --------------------------------------
    narratives: dict[str, str] = {}
    fallback_sections: list[str] = []
    sections = ["executive_summary"] + [d for d, s in scores.items() if s.assessed]

    for section in sections:
        context = _section_context(section, client_name, scores, overall, overall_band, config)

        if active is not fallback:
            try:
                guard.tick()
                governor.pre_call(_estimate_tokens(context))
                governor.record_action("narrative_sections")
            except (BudgetExceededError, LoopLimitError) as exc:
                component = "loop_guard" if isinstance(exc, LoopLimitError) else "cost_governor"
                audit.record_intervention(
                    action=f"narrate:{section}",
                    component=component,
                    prevented=str(exc),
                    reason="degrading to rule-based narration for the remaining sections",
                    **tags,
                )
                active = fallback

        used_fallback = active is fallback
        narration = active.narrate(section, context)

        if not used_fallback:
            try:
                governor.post_call(narration.tokens_used, narration.cost_usd)
            except BudgetExceededError as exc:
                # The spend already happened — keep the paid-for text, degrade from here on.
                audit.record_intervention(
                    action=f"narrate:{section}",
                    component="cost_governor",
                    prevented=str(exc),
                    reason="spend cap crossed after the call; remaining sections degrade",
                    **tags,
                )
                active = fallback

        narratives[section] = narration.text
        if used_fallback:
            fallback_sections.append(section)
        audit.record(
            action=f"narrate:{section}",
            decision="allowed",
            outputs={
                "tokens": narration.tokens_used,
                "cost_usd": narration.cost_usd,
                "fallback": used_fallback,
            },
            **tags,
        )

    return Assessment(
        client_name=client_name,
        run_id=run_id,
        collector_results=results,
        findings=findings,
        scores=scores,
        overall=overall,
        narratives=narratives,
        config=config,
        fallback_sections=fallback_sections,
        audit=audit,
        governor=governor,
        limits=limits,
    )
