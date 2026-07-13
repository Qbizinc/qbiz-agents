# Assay — Data & AI Readiness Assessment Agent

*Design doc & build plan. Status: Phase 1 scaffold built (2026-07-09). Owner: David Sevier.*

---

## The problem this sells against

Every prospect conversation in the data space now includes "we want to use AI, and we're not
sure we're doing it right." Underneath that sentence live the same recurring problems we see
across Data Engineering, Analytics, and Data Science:

| Space | Recurring problem | What it looks like in the artifacts |
| --- | --- | --- |
| Data Engineering | Silent breakage, firefighting | Untested models, sources with no freshness SLAs, DAGs whose failures notify nobody |
| Data Engineering | Surprise compute spend | `catchup=True` backfills, unbounded retries, no cost attribution |
| Analytics | Tribal knowledge, no trust | Undocumented models, reverse-engineering intent from SQL |
| Analytics / Governance | PII exposure risk | No sensitivity classification anywhere — nobody can say what an agent *must not* read |
| Data Science / AI | Ungoverned LLM usage | Provider SDKs called directly from notebooks and scripts: no cost caps, no loop bounds, no audit trail, occasionally a hardcoded key |
| All three | "POC purgatory" | AI experiments that can never ship because nothing about them is defensible to security or finance |

**Assay is a governed agent that scans a prospect's data estate and turns those problems into
a scored, evidence-backed readiness report** — with a remediation roadmap that maps each gap
to the Qbiz engagement that retires it.

## Why this tool (vs. the other candidates)

Ranked against the alternatives from the AI-consulting positioning work (migration agent, dbt
generator, data-quality triage, NL-to-analytics):

1. **It is the direct answer to the positioning goal** — "companies trying to learn how to use
   AI well, both effectiveness and efficiency." An assessment *is* that conversation, productized.
2. **It's a pre-sales lever.** Run it in discovery from three artifacts a prospect can share in
   an hour (dbt `manifest.json`, DAG folder, repo read access). The report's roadmap is a
   proposal skeleton: every finding names the offering that fixes it.
3. **It's the meta-demo of the harness.** The assessment itself runs under `qbiz_harness` —
   cost-capped, loop-bounded, redundancy-guarded, audited — and the report's final section
   discloses the numbers. "The report you're holding was produced by a governed agent" is the
   pitch, delivered by the deliverable.
4. **It's unblocked.** Collectors and scoring are deterministic (no LLM, no key, no `[D3]`
   provider decision). The only LLM stage — narrative — sits behind a Protocol with a
   deterministic fallback, so the whole thing ships and demos today.
5. **It compounds.** Every heuristic a consultant learns on an engagement becomes a collector
   check; every engagement makes the next assessment sharper. That is exactly the qbiz-agents
   thesis applied to sales.

The migration agent remains the bigger *revenue* play, but it needs a legacy corpus to demo
and a much larger build. Assay is the wedge that gets us into that conversation.

## Architecture

**Deterministic-first, LLM-last.** That IS the effectiveness-and-efficiency story, embodied:

```
 artifacts                stage                     cost      trust
 ──────────               ─────────────────────    ─────     ─────────────────────────
 manifest.json     ┌──►   collectors (parsing)     free      facts — never LLM output
 DAG folder        │      rubric (arithmetic)      free      reproducible scores
 repo access       │      narrator (LLM)           metered   explains, cannot alter facts
                   │      report (markdown)        free      roadmap → Qbiz offerings
                   └──    all of it under qbiz_harness: CostGovernor, LoopGuard, AuditLog
```

- `src/qbiz_assay/findings.py` — the vocabulary: `Finding(dimension, severity, title, detail,
  remediation, offering, subject)`. Findings are parsed facts. The narrator may *explain* them
  but can never add, remove, or reword one — that separation is what makes the report
  defensible in front of a client.
- `collectors/` — one module per artifact type, all pure parsing, no network, no execution:
  - `dbt.py` — manifest.json: test coverage, doc coverage, **sensitivity-classification
    coverage** (ties directly to the Data Sensitivity proposal in the startup kit), source
    freshness.
  - `airflow.py` — AST-scan of DAG files (never imported, never executed): retries, failure
    callbacks (does a failure *go* anywhere? → incident-agent offering), ownership,
    `catchup=True` cost bombs.
  - `ai_usage.py` — the headline scan: where does this company already call LLMs, and does
    anything govern it? Import-based provider detection + hardcoded-credential regex.
- `rubric.py` — six dimensions (Data Quality, Documentation, Governance & Sensitivity,
  Operations, Cost, AI Governance), 100 minus severity-weighted deductions. A dimension nothing
  assessed reports **"Not assessed"** — never a silent 100. Scores are arithmetic, not vibes.
- `assessor.py` — `Narrator` Protocol (mirrors the harness's `ApprovalTransport` injection
  pattern). `RuleBasedNarrator` is both the no-key default and the **fallback path** when the
  governor cuts off a runaway LLM narrator.
- `engine.py` — the harness call site. Collectors run under the redundancy guard; narration is
  metered (`pre_call` token estimate → `post_call` actuals → action cap on section count);
  every event lands in the `AuditLog` tagged `cohort="assay"` with a per-run `incident_id`.
  On any `BudgetExceededError`/`LoopLimitError`: record the intervention, degrade to the
  deterministic narrator, **finish the assessment anyway**. Governed degradation, never
  half-failure.
- `report.py` — the client deliverable: scorecard → executive summary → per-dimension detail →
  roadmap grouped by offering (ordered by risk retired) → **"How this assessment was
  produced"** (tokens, spend, caps, interventions, audit-trail path).

Dependency direction honors the repo rule: `qbiz_assay` imports `qbiz_harness`; nothing
imports back. Assay is the harness's **second consumer**, which is itself useful — it
validates that the one-way-dependency design holds beyond the original agents.

## Demo

`demo/assess_acme.py` — no-LLM, no-key, narrated in five scenes (same format as
`harness/demo/incident_runaway.py`): synthetic client "Acme Analytics" (fixtures under
`demo/fixtures/acme/`: a 6-model manifest with poor coverage, two smelly DAGs, two ungoverned
LLM scripts, two hardcoded credentials). A scripted **runaway narrator** burns 4× more tokens
per section; the spend cap kills it mid-run; a deliberate duplicate collection trips the
redundancy guard; the assessment completes on the fallback and writes `demo/out/REPORT_acme.md`
plus the JSONL audit trail.

Run: `uv run python demo/assess_acme.py` (or plain `python`, ≥3.11 — sys.path shims included).

## Build phases

- **Phase 1 — scaffold (DONE 2026-07-09):** everything described above, plus tests.
- **Phase 2 — real narrator + real connectors:**
  - LLM narrator behind the existing Protocol (pydantic-ai, consistent with the incident DAG;
    provider choice inherits the open `[D3]`/LLM-provider decision — nothing here blocks on it).
  - Warehouse cost connector (Snowflake `QUERY_HISTORY` / BigQuery `INFORMATION_SCHEMA.JOBS`):
    turns the Cost dimension from partial signals into real hotspot findings.
  - dbt Cloud / Fusion artifact ingestion (today assumes a Core-style manifest).
  - `qba assay run <config>` CLI entry so consultants run it like any other qbiz-agents tool.
- **Phase 3 — the compounding layer:**
  - **HITL gate on external delivery** (harness Component 8 via Slack MCP): a human approves
    before a report leaves the building — dogfooding the approval flow.
  - **Re-assessment trend line** (RAG MCP as the store, same library-embed pattern as the
    incident memory): re-run each quarter, show score deltas — turns a one-shot assessment
    into a retainer.
  - Anonymized cross-client benchmark ("you're in the bottom quartile for test coverage") —
    **needs an explicit data-ethics/consent decision before any pooling.**

## Open decisions

- **[A1] Delivery form:** consultant-run CLI (current), client-runnable self-serve, or both?
  Self-serve is a lead magnet but exposes the rubric to gaming.
- **[A2] Benchmark pooling:** consent model and anonymization bar for cross-client comparisons.
- **[A3] Rubric weights:** current severity weights (40/25/10/4/0) are sensible defaults;
  calibrate against a few real engagements before anyone quotes a score externally. Per the
  standing principle: a client's own standards override the Qbiz baseline — weights and
  thresholds must stay config, not code.
- **[A4] Scope creep guard:** collectors must stay read-only forever. The moment Assay *fixes*
  things it competes with the engagements it's meant to sell, and its risk tier jumps.

## Presentation tie-in (internal deck, 2026-07)

Assay is the "where we go from here" slide made concrete: the landscape shifted from
generation to verification/judgment/accountability — and Assay is literally a product that
sells judgment (scored findings), verification (evidence-backed, reproducible), and
accountability (audit trail in the deliverable). One slide, one demo run, one report page.
