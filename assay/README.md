# qbiz-assay

**Data & AI readiness assessment, governed by the Qbiz harness.**

Assay scans a client's data estate — dbt project, Airflow DAGs, repo-wide AI usage — with
deterministic collectors, scores it against a six-dimension readiness rubric, and renders a
client-facing report whose remediation roadmap maps every finding to the Qbiz offering that
retires it. The only LLM stage (narrative) runs metered under
[`qbiz_harness`](../harness/README.md), so every report is a live demonstration of governed
agent operation — and says so, with numbers, in its final section.

Design, rationale, and build phases: [ASSAY_PLAN.md](ASSAY_PLAN.md).

## Quick start

```bash
# The narrated end-to-end demo (no LLM, no API key needed):
uv run python demo/assess_acme.py

# Tests:
uv run pytest tests/ -q
```

The demo assesses a synthetic client ("Acme Analytics"), lets a scripted runaway narrator get
capped by the CostGovernor mid-run, and writes `demo/out/REPORT_acme.md` plus a JSONL audit
trail.

## What gets assessed

| Dimension | Signal source (Phase 1) |
| --- | --- |
| Data Quality & Testing | dbt manifest: test coverage, source freshness |
| Documentation & Discoverability | dbt manifest: description coverage |
| Governance & Data Sensitivity | dbt `sensitivity` meta coverage; repo credential scan |
| Operational Maturity | Airflow DAG AST scan: retries, failure callbacks, ownership |
| Cost Efficiency | `catchup=True` bombs (warehouse query-history connector is Phase 2) |
| AI Readiness & Governance | ungoverned LLM call sites, missing audit trail |

Inputs are artifacts a prospect can share in an hour: `target/manifest.json`, a DAG folder,
repo read access. Collectors are pure parsing — nothing is imported, executed, or sent anywhere.

## Using it as a library

```python
from functools import partial
from qbiz_assay import run_assessment, render_markdown
from qbiz_assay.collectors import dbt, airflow, ai_usage

assessment = run_assessment(
    client_name="Acme Analytics",
    collectors=[
        ("dbt-manifest", partial(dbt.collect, "path/to/manifest.json")),
        ("airflow-dags", partial(airflow.collect, "path/to/dags")),
        ("ai-usage", partial(ai_usage.collect, "path/to/repo")),
    ],
)
print(render_markdown(assessment))
```

Pass a `narrator=` implementing the `Narrator` protocol to use an LLM for the prose; omit it
for the deterministic rule-based narration. Either way the engine meters usage through the
harness and finishes the report even if the narrator is cut off.
