"""Narrative layer — the only place an LLM ever touches the assessment.

Findings and scores are deterministic; the narrator only *explains* them. It is injected as a
Protocol (mirroring the harness's ``ApprovalTransport`` pattern) so the engine, tests, and demo
run with no API key and no provider decision, and a real LLM narrator can be swapped in later
without touching the engine. Every narrator call is metered through the CostGovernor by the
engine — the narrator itself never sees the budget.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class NarrationResult:
    """One narrated section, plus what producing it cost (zero for rule-based)."""

    text: str
    tokens_used: int = 0
    cost_usd: float = 0.0


class Narrator(Protocol):
    """Anything that can turn a section context into prose.

    ``section`` is ``"executive_summary"`` or a ``Dimension`` value; ``context`` is the
    engine-built summary of scores and top findings for that section (see
    ``engine._section_context``). Implementations must report actual token/cost usage in the
    result so the governor can meter them.
    """

    def narrate(self, section: str, context: dict[str, object]) -> NarrationResult: ...


class RuleBasedNarrator:
    """Deterministic, zero-cost narration from templates.

    Serves two jobs: the *fallback path* when the harness cuts off a runaway LLM narrator
    (a governed assessment always completes — it never half-fails), and the default for
    demos and tests, which need no API key.
    """

    def narrate(self, section: str, context: dict[str, object]) -> NarrationResult:
        if section == "executive_summary":
            return NarrationResult(text=self._executive_summary(context))
        return NarrationResult(text=self._dimension(context))

    @staticmethod
    def _executive_summary(context: dict[str, object]) -> str:
        client = context.get("client_name", "The client")
        overall = context.get("overall")
        band = context.get("band", "")
        dims = [d for d in context.get("dimensions", []) if d.get("score") is not None]  # type: ignore[union-attr]
        total = context.get("finding_count", 0)
        critical = context.get("critical_count", 0)

        if overall is None or not dims:
            return f"{client}: no dimensions could be assessed from the artifacts provided."

        strongest = max(dims, key=lambda d: d["score"])
        weakest = min(dims, key=lambda d: d["score"])
        parts = [
            f"{client} scores {overall}/100 overall — {band}.",
            f"Strongest dimension: {strongest['title']} ({strongest['score']}/100).",
            f"Most exposed: {weakest['title']} ({weakest['score']}/100).",
            f"The assessment surfaced {total} finding(s)"
            + (f", {critical} of them critical." if critical else "."),
        ]
        if critical:
            parts.append("Critical items are remediate-now: they are exposures, not backlog.")
        return " ".join(parts)

    @staticmethod
    def _dimension(context: dict[str, object]) -> str:
        title = context.get("title", "This dimension")
        score = context.get("score")
        band = context.get("band", "")
        findings = list(context.get("findings", []))  # type: ignore[arg-type]

        if not findings:
            return f"{title} scores {score}/100 ({band}). No issues surfaced in this pass."
        top = findings[0]
        text = (
            f"{title} scores {score}/100 ({band}). "
            f"Leading issue: {top['title']}. "
            f"Recommended first step: {top['remediation']}"
        )
        if len(findings) > 1:
            text += f" ({len(findings) - 1} further finding(s) detailed below.)"
        return text
