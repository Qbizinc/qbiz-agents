# qbiz-assay

**Data & AI discovery assessment framework, governed by the Qbiz harness.**

Assay scans a client's data estate with deterministic collectors, scores it against a
config-driven readiness rubric, and renders a client-facing report whose remediation roadmap
maps every finding to the Qbiz offering that retires it. The only LLM stage (narrative) runs
metered under [`qbiz_harness`](../harness/README.md), so every report is a live demonstration
of governed agent operation — and says so, with numbers, in its final section.

It is a *framework*: the engine, rubric, and report iterate registries — dimensions, weights,
bands, offerings, and collectors are data, not code. Adding a check for a new part of a
client's stack is one small plugin file; adding a dimension or retuning the rubric is YAML.

Design, rationale, and build phases: [ASSAY_PLAN.md](ASSAY_PLAN.md).
Writing a collector or an engagement profile: [docs/EXTENDING.md](docs/EXTENDING.md).

## Quick start

```bash
# The narrated end-to-end demo (no LLM, no API key needed):
uv run python demo/assess_acme.py

# The same assessment, profile-driven, via the CLI:
uv run qba assay run demo/acme_profile.yaml --report demo/out/REPORT_acme_cli.md

# What checks exist and what each needs from a client:
uv run qba assay list-collectors

# Tests:
uv run pytest tests/ -q
```

The demo assesses a synthetic client ("Acme Analytics"), lets a scripted runaway narrator get
capped by the CostGovernor mid-run, and writes `demo/out/REPORT_acme.md` plus a JSONL audit
trail.

## Delivery modes

- **Pulse check** — shareable artifacts only (a dbt `manifest.json`, a DAG folder, repo read
  access). **Zero credentials, enforced**: a pulse profile cannot enable a connected
  collector. Runs in about an hour of a prospect's time.
- **Full assessment** — adds connected collectors (read-only queries against live systems,
  through shared MCP servers) and, in a later phase, structured interviews.

## What gets assessed (baseline rubric)

| Dimension | Signal source |
| --- | --- |
| Data Quality & Testing | dbt manifest: test coverage, source freshness |
| Documentation & Discoverability | dbt manifest: description coverage |
| Governance & Data Sensitivity | dbt `sensitivity` meta coverage; repo credential scan |
| Operational Maturity | Airflow DAG AST scan: retries, failure callbacks, ownership |
| Cost Efficiency | `catchup=True` bombs (warehouse query-history collector is Phase 3) |
| AI Readiness & Governance | ungoverned LLM call sites, missing audit trail |
| Cloud Security Posture* | `aws` MCP server: public buckets, unencrypted storage, over-broad IAM |

\* `cloud_posture` is a connected-mode, profile-added dimension — the worked example of
extending the framework (see EXTENDING.md).

Dimensions, weights, bands, and the offering catalog live in
[`config/qbiz_baseline.yaml`](src/qbiz_assay/config/qbiz_baseline.yaml); an engagement profile
overrides any of it per client.

## Running an engagement

One YAML profile per client is the entry point:

```yaml
client: Acme Analytics
mode: pulse
collectors:
  - name: dbt-manifest
    inputs:
      manifest_path: artifacts/dbt/manifest.json
rubric:
  dimensions:
    - id: data_quality
      weight: 2.0
```

```bash
uv run qba assay run profile.yaml --report REPORT.md --audit audit.jsonl
```

## Using it as a library

```python
from qbiz_assay import run_profile, render_markdown

assessment = run_profile("profile.yaml")
print(render_markdown(assessment))
```

Or wire collectors by hand with `run_assessment(client_name=..., collectors=[(name, fn), ...])`.
Pass a `narrator=` implementing the `Narrator` protocol to use an LLM for the prose; omit it
for the deterministic rule-based narration. Either way the engine meters usage through the
harness and finishes the report even if the narrator is cut off.
