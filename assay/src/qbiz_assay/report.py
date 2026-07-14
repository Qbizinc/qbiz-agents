"""Markdown report renderer — the client-facing artifact.

Layout: scorecard → executive summary → per-dimension detail → a roadmap that groups findings
by the Qbiz offering that addresses them (ordered by how much risk each group retires). The
final section discloses how the assessment itself was governed — tokens, spend, interventions —
because "this report was produced by an agent running under the same harness we sell" *is*
the pitch, and it should be visible in the deliverable, not just the deck.

The renderer is generic machinery: dimensions (and their order and titles) come from the
assessment's rubric registry, offering titles from its catalog. Findings carry an evidence
type; where a dimension's evidence is not purely parsed artifacts, the report says so — a
score built on attestations must never look like a score built on scans.
"""

from __future__ import annotations

from datetime import date

from qbiz_assay.engine import Assessment
from qbiz_assay.findings import SEVERITY_ORDER, EvidenceType, Finding


def _sorted_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: SEVERITY_ORDER[f.severity])


_EVIDENCE_LABELS: dict[EvidenceType, str] = {
    EvidenceType.ARTIFACT: "parsed from shared artifacts",
    EvidenceType.SYSTEM_OF_RECORD: "queried from the system of record",
    EvidenceType.ATTESTATION: "attested in interviews (not independently verified)",
}


def _evidence_note(findings: list[Finding]) -> str | None:
    """One line on where a dimension's evidence came from, when any of it wasn't parsed."""
    kinds = {f.evidence for f in findings}
    if not kinds or kinds == {EvidenceType.ARTIFACT}:
        return None
    labels = [_EVIDENCE_LABELS[k] for k in EvidenceType if k in kinds]
    return f"_Evidence: {'; '.join(labels)}._"


def render_markdown(assessment: Assessment, *, audit_path: str | None = None) -> str:
    rubric = assessment.config.rubric
    lines: list[str] = []
    out = lines.append

    out(f"# Data & AI Readiness Assessment — {assessment.client_name}")
    out("")
    out(
        f"_Prepared by **Assay** (qbiz-agents), a harness-governed assessment agent. "
        f"Run `{assessment.run_id}`, {date.today().isoformat()}._"
    )

    # --- Scorecard --------------------------------------------------------------------------
    out("")
    out("## Scorecard")
    out("")
    out("| Dimension | Score | Band | Findings |")
    out("| --- | ---: | --- | ---: |")
    for dim, score in assessment.scores.items():
        shown = str(score.score) if score.score is not None else "—"
        out(f"| {rubric.title_for(dim)} | {shown} | {score.band} | {len(score.findings)} |")
    overall = str(assessment.overall) if assessment.overall is not None else "—"
    out(f"| **Overall** | **{overall}** | | **{len(assessment.findings)}** |")

    unassessed = [rubric.title_for(d) for d, s in assessment.scores.items() if not s.assessed]
    if unassessed:
        out("")
        out(
            f"_Not assessed in this pass: {', '.join(unassessed)} — needs artifacts or "
            "connectors not included in this run (see roadmap)._"
        )

    # --- Executive summary --------------------------------------------------------------------
    out("")
    out("## Executive summary")
    out("")
    out(assessment.narratives.get("executive_summary", "_No narrative produced._"))

    # --- Per-dimension detail ------------------------------------------------------------------
    for dim, score in assessment.scores.items():
        if not score.assessed:
            continue
        out("")
        out(f"## {rubric.title_for(dim)} — {score.score}/100 ({score.band})")
        out("")
        narrative = assessment.narratives.get(dim)
        if narrative:
            out(narrative)
        note = _evidence_note(score.findings)
        if note:
            out("")
            out(note)
        if score.findings:
            out("")
            out("| Severity | Finding | Where | Recommended remediation |")
            out("| --- | --- | --- | --- |")
            for f in _sorted_findings(score.findings):
                subject = f.subject or "—"
                out(f"| {f.severity.value.upper()} | {f.title} | `{subject}` | {f.remediation} |")

    # --- Roadmap ---------------------------------------------------------------------------------
    by_offering: dict[str, list[Finding]] = {}
    for f in assessment.findings:
        if f.offering:
            by_offering.setdefault(f.offering, []).append(f)
    if by_offering:
        out("")
        out("## Recommended roadmap")
        out("")
        out("Findings grouped by the engagement that retires them, highest-risk group first.")
        ranked = sorted(
            by_offering.items(),
            key=lambda kv: -sum(rubric.deduction_for(f.severity) for f in kv[1]),
        )
        for i, (offering, group) in enumerate(ranked, start=1):
            out("")
            out(f"### {i}. {assessment.config.offering_title(offering)}")
            for f in _sorted_findings(group):
                out(f"- **{f.title}** — {f.remediation}")

    # --- Governance disclosure -------------------------------------------------------------------
    out("")
    out("## How this assessment was produced")
    out("")
    gov = assessment.governor
    collectors = ", ".join(r.name for r in assessment.collector_results) or "none"
    out(f"- **Deterministic collectors** (zero tokens): {collectors}.")
    llm_sections = [
        s for s in assessment.narratives if s not in assessment.fallback_sections
    ]
    out(
        f"- **Narration**: {len(llm_sections)} section(s) narrated by the metered narrator, "
        f"{len(assessment.fallback_sections)} by the deterministic fallback."
    )
    if gov is not None:
        line = (
            f"- **Budget**: {gov.tokens_used:,} tokens / ${gov.spend_usd:.2f} spent, against "
            f"caps of {gov.token_limit:,} tokens / ${gov.spend_limit:.2f}."
        )
        if gov.spend_usd > gov.spend_limit or gov.tokens_used > gov.token_limit:
            line += (
                " The final metered call crossed the cap on post-call accounting; the "
                "governor halted all further metered work at that point (see interventions)."
            )
        out(line)
    counts = assessment.audit.intervention_counts()
    if counts:
        summary = ", ".join(f"{component} ×{n}" for component, n in sorted(counts.items()))
        out(
            f"- **Harness interventions**: {summary}. Each one is in the audit trail with what "
            "it prevented. The assessment completed anyway — governed degradation, not failure."
        )
    else:
        out("- **Harness interventions**: none — the agent stayed within bounds.")
    out(f"- **Audit trail**: `{audit_path or 'in-memory (pass a path to persist)'}`")
    out("")
    out(
        "_Every number above was enforced in code by the Qbiz Agent Harness — the same "
        "governance layer Qbiz deploys around client-facing agents._"
    )
    out("")

    return "\n".join(lines)
