#!/usr/bin/env python3
"""Assay demo — a governed AI readiness assessment, end to end, with no LLM.

The scenario: a prospect ("Acme Analytics") hands us three artifacts — their dbt
``manifest.json``, their Airflow DAG folder, and read access to a repo. Assay:

    1. **Collects** deterministically (pure parsing — zero tokens, zero risk),
    2. **Scores** a six-dimension readiness rubric (arithmetic, not vibes),
    3. **Narrates** the findings — the only LLM stage, metered by the harness,
    4. **Renders** a client-facing report whose roadmap maps findings to Qbiz offerings.

To show the harness working, the narrator here is scripted to misbehave — every call burns
4× the tokens of the last, the way a context-stuffing loop does. The CostGovernor cuts it
off mid-run and the engine degrades to the deterministic narrator: the assessment always
completes. We also ask Assay to re-scan an artifact it already scanned — the redundancy
guard refuses.

The takeaway matches the harness demo's:

    "Instructions are a request. The harness is enforcement."

Run it:
    uv run python demo/assess_acme.py
    # or, without installing:  python demo/assess_acme.py
"""

from __future__ import annotations

import functools
import os
import sys
from pathlib import Path

# Windows consoles default to cp1252 and choke on the box-drawing / emoji glyphs below.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

# Let the demo run straight from the repo without an install step.
_ASSAY_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ASSAY_ROOT / "src"))
sys.path.insert(0, str(_ASSAY_ROOT.parent / "harness" / "src"))

from qbiz_harness import AuditLog  # noqa: E402

from qbiz_assay import (  # noqa: E402
    DIMENSION_TITLES,
    AssessmentLimits,
    Dimension,
    NarrationResult,
    RuleBasedNarrator,
    render_markdown,
    run_assessment,
)
from qbiz_assay.collectors import ai_usage, airflow, dbt  # noqa: E402
from qbiz_assay.rubric import overall_score, score_dimensions  # noqa: E402

CLIENT = "Acme Analytics"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "acme"
OUT_DIR = Path(__file__).resolve().parent / "out"


# --- tiny terminal styling (dependency-free; respects NO_COLOR and non-tty) -------------------

_USE_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def bold(t: str) -> str:
    return _c("1", t)


def green(t: str) -> str:
    return _c("32", t)


def red(t: str) -> str:
    return _c("31", t)


def yellow(t: str) -> str:
    return _c("33", t)


def dim(t: str) -> str:
    return _c("2", t)


def scene(title: str) -> None:
    print("\n" + bold("━" * 70))
    print(bold(title))
    print(bold("━" * 70))


def ok(msg: str) -> None:
    print(f"  {green('✓')}  {msg}")


def blocked(msg: str) -> None:
    print(f"  {red('✗ BLOCKED')}  {msg}")


def note(msg: str) -> None:
    print(f"  {yellow('▸')}  {msg}")


def agent_says(msg: str) -> None:
    print(f"  {dim('narrator ▸')} {dim(msg)}")


# --- the misbehaving narrator ------------------------------------------------------------------
#
# Text comes from the rule-based templates (so the demo needs no key); the *usage numbers* are
# scripted to grow 4× per call — the shape of a real context-stuffing loop. The engine meters
# usage through the CostGovernor, which is the point: the narrator does not decide its budget.


class RunawayNarrator:
    """An 'LLM narrator' that gets greedier with every section it writes."""

    def __init__(self) -> None:
        self._inner = RuleBasedNarrator()
        self._calls = 0

    def narrate(self, section: str, context: dict[str, object]) -> NarrationResult:
        self._calls += 1
        tokens = 600 * (4 ** (self._calls - 1))  # 600 → 2,400 → 9,600 → 38,400 → 153,600
        cost = round(tokens * 0.000015, 4)
        agent_says(f"drafting {section!r} … used {tokens:,} tokens (${cost:.2f})")
        base = self._inner.narrate(section, context)
        return NarrationResult(text=base.text, tokens_used=tokens, cost_usd=cost)


def main() -> None:
    print(bold("\nASSAY — governed Data & AI readiness assessment (no-LLM demo)"))
    print(dim("Everything below is enforced in code by qbiz_harness. No API key required."))

    # --- Scene 1 -------------------------------------------------------------------------------
    scene("SCENE 1 — The prospect hands over three artifacts")
    print(f"""
  Client: {bold(CLIENT)}
    • dbt compile artifact   {dim(str(FIXTURES / 'dbt' / 'manifest.json'))}
    • Airflow DAG folder     {dim(str(FIXTURES / 'dags'))}
    • repo read access       {dim(str(FIXTURES))}
""".rstrip())

    # --- Scene 2 -------------------------------------------------------------------------------
    scene("SCENE 2 — Deterministic collection (pure parsing, zero tokens)")
    dbt_result = dbt.collect(FIXTURES / "dbt" / "manifest.json")
    airflow_result = airflow.collect(FIXTURES / "dags")
    ai_result = ai_usage.collect(FIXTURES)

    s = dbt_result.stats
    ok(
        f"dbt: {s['models']} models — tests {s['test_coverage_pct']}%, docs "
        f"{s['doc_coverage_pct']}%, sensitivity tags {s['sensitivity_coverage_pct']}%"
    )
    s = airflow_result.stats
    ok(f"airflow: {s['dags']} DAGs — {s['dags_without_failure_callback']} with NO failure callback")
    s = ai_result.stats
    ok(
        f"ai-usage: {s['llm_call_sites']} LLM call sites ({', '.join(s['providers'])}), "
        f"{s['governed_call_sites']} governed, {s['files_with_hardcoded_credentials']} "
        f"file(s) with hardcoded credentials"
    )
    results = [dbt_result, airflow_result, ai_result]
    findings = [f for r in results for f in r.findings]
    note(f"{len(findings)} findings — every one a parsed fact, not an opinion")

    # --- Scene 3 -------------------------------------------------------------------------------
    scene("SCENE 3 — Scoring the rubric (arithmetic, not vibes)")
    assessed: set[Dimension] = set()
    for r in results:
        assessed |= r.dimensions
    scores = score_dimensions(findings, assessed)
    for dimension in Dimension:
        score = scores[dimension]
        shown = f"{score.score:>3}/100" if score.score is not None else "  —    "
        print(f"    {DIMENSION_TITLES[dimension]:<34} {shown}  {score.band}")
    print(f"    {'Overall':<34} {overall_score(scores):>3}/100")

    # --- Scene 4 -------------------------------------------------------------------------------
    scene("SCENE 4 — Narration under the harness (watch the caps work)")
    print(dim("  Limits: $1.00 spend cap, 60k tokens, 10 narrative sections, 24 iterations."))
    print(dim("  The narrator is scripted to burn 4× more tokens per section — a runaway.\n"))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    audit_path = OUT_DIR / "audit_acme.jsonl"
    audit_path.unlink(missing_ok=True)  # fresh trail each run
    audit = AuditLog(path=audit_path)

    # Cached collectors so scene 2's parse is reused — plus a deliberate duplicate:
    # a confused agent asks to re-scan the dbt manifest it already scanned.
    collectors = [
        ("dbt-manifest", lambda: dbt_result),
        ("airflow-dags", lambda: airflow_result),
        ("ai-usage", lambda: ai_result),
        ("dbt-manifest", lambda: dbt_result),  # ← redundant on purpose
    ]

    assessment = run_assessment(
        client_name=CLIENT,
        collectors=collectors,
        narrator=RunawayNarrator(),
        audit=audit,
        limits=AssessmentLimits(spend_limit_usd=1.00),
    )

    print()
    for event in assessment.audit.interventions():
        component = event.intervention.component if event.intervention else "?"
        blocked(f"[{component}] {event.intervention.prevented if event.intervention else ''}")
    if assessment.fallback_sections:
        note(
            f"engine degraded to the deterministic narrator for: "
            f"{', '.join(assessment.fallback_sections)}"
        )
    gov = assessment.governor
    assert gov is not None
    ok(
        f"assessment still completed — {len(assessment.narratives)} sections, "
        f"${gov.spend_usd:.2f} spent against the ${gov.spend_limit:.2f} cap"
    )

    # --- Scene 5 -------------------------------------------------------------------------------
    scene("SCENE 5 — The deliverable")
    report_path = OUT_DIR / "REPORT_acme.md"
    report_path.write_text(
        render_markdown(assessment, audit_path=str(audit_path)), encoding="utf-8"
    )
    counts = assessment.audit.intervention_counts()
    summary = ", ".join(f"{component} ×{n}" for component, n in sorted(counts.items()))
    ok(f"report written:      {report_path}")
    ok(f"audit trail written: {audit_path} ({len(assessment.audit.events)} events)")
    note(f"harness interventions this run: {summary or 'none'}")

    print(f"""
  {bold('The takeaway for the room:')}

    The report Acme receives was produced by an agent that was itself governed —
    cost-capped, loop-bounded, audited — by the same harness Qbiz sells. The last
    section of the report {bold('shows the client the interventions')}. That is the pitch:

        {bold('"Generation is cheap. Governed generation is what you can')}
        {bold(' put in front of a client."')}
""")


if __name__ == "__main__":
    main()
