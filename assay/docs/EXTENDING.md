# Extending Assay

Assay is a discovery *framework*: the engine, rubric, and report are generic machinery that
iterate registries, and everything domain-specific — dimensions, weights, bands, offerings,
collectors — is data or one small plugin. This guide is the Tier-1 authoring path: **a new
collector should take under a day, most an hour or two.** If anything here forces you to edit
`engine.py`, `rubric.py`, or `report.py`, stop — that is a framework bug; file it instead of
routing around it.

## The extension ladder

| Tier | What changes | Effort |
| --- | --- | --- |
| **0 — config only** | An engagement profile: enable/disable collectors, retune weights and bands, rename dimensions, remap offerings, add a dimension or offering | Minutes |
| **1 — one new collector** | One Python file implementing the contract, plus Tier-0 config entries | Under a day; most in an hour or two |
| **2 — core enhancement** | A new acquisition mode or engine capability | Rare, planned work — talk to the framework owner first |

## Tier 0 — the engagement profile

One YAML file per client is the whole "plug into their stack" step for anything the collector
library already covers:

```yaml
client: Acme Analytics
mode: pulse                    # pulse = shareable artifacts only, zero credentials (enforced)
collectors:
  - name: dbt-manifest
    inputs:
      manifest_path: artifacts/dbt/manifest.json   # relative to this file
  - name: airflow-dags
    inputs:
      dags_dir: artifacts/dags
rubric:                        # optional, partial — merged over config/qbiz_baseline.yaml
  dimensions:
    - id: data_quality
      weight: 2.0              # client cares most about quality: weight it up
    - id: cloud_posture        # new id = new dimension, appended to the rubric
      title: Cloud Security Posture
offerings:
  cloud_security_review:
    title: Cloud Security Review
limits:
  spend_limit_usd: 1.00
```

Run it: `qba assay run profile.yaml --report REPORT.md --audit audit.jsonl`.
See what you can enable: `qba assay list-collectors`.

Merge semantics: dimensions and offerings merge **by id** (listed fields override, new ids
append); `severity_weights` merges per severity; `bands` replaces wholesale. The baseline is
the Qbiz default — a client's own standards beat it, which is exactly what the override is
for.

## Tier 1 — writing a collector

Start from [`collectors/TEMPLATE.py`](../src/qbiz_assay/collectors/TEMPLATE.py) and
[`tests/test_collector_TEMPLATE.py`](../tests/test_collector_TEMPLATE.py). Both are live code
— the template is registered and tested, so it cannot rot.

The contract, in full:

1. **Declare, don't wire.** The `@collector` decorator carries your metadata: unique `name`,
   the `dimensions` you assess, exactly one acquisition `mode`, an `inputs` map (keyword
   argument → human description of what to pass), and `requires_mcp` for connected mode.
   Registration is discovery: `list-collectors`, profile validation, and the engine all read
   the registry — there is no call site to edit anywhere.
2. **Match your signature to your `inputs` keys.** Profiles bind inputs by keyword.
3. **Findings are deterministic facts.** Parse, query, or record — never guess, never call an
   LLM. The narrator explains findings; it can never add, remove, or reword one.
4. **Never raise on messy input.** A broken artifact is itself a finding. A collector that
   crashes takes the engagement run with it.
5. **Read-only forever, in every mode** (open decision [A4], but the principle is settled).
   The moment Assay *fixes* things it competes with the engagements it sells, and its risk
   tier jumps.
6. **Set `evidence` honestly.** `artifact` (default) when you parsed it, `system-of-record`
   when you queried it, `attestation` when someone told you. The report distinguishes them —
   a score built on attestations must say so.

### Acquisition modes

- **artifact** — offline parsing of files the client shared. Zero credentials, zero network;
  the only mode the pulse tier allows (the loader enforces this — it is what makes the pulse
  check something a prospect will agree to). Input values are paths, resolved relative to the
  profile file.
- **connected** — read-only queries against live systems, **always through a shared MCP
  server**, never a provider SDK inside Assay. Declare the server in `requires_mcp` (the
  registry rejects a connected collector without one). In a profile, the input value
  `"mcp:<server>"` resolves to the live tool caller passed to `run_profile`. Before writing
  one, run the reuse checklist in ASSAY_PLAN.md ("Reuse over duplication"): existing server →
  in-flight server → build the server first → only then Assay-internal. The worked example is
  [`collectors/cloud_posture.py`](../src/qbiz_assay/collectors/cloud_posture.py), a thin
  caller of the merged `mcp/mcp_aws` server.
- **interview** — structured questionnaires; answers become `attestation` findings. The
  questionnaire plumbing is Phase 4; declaring the mode already works.

### New dimension or offering?

Tier 0, not code: add it to the engagement profile (or, once several engagements want it, to
`config/qbiz_baseline.yaml`). A finding tagged with an unregistered dimension still scores —
evidence trumps registration — but shows its raw id as the title, so register what you ship.

### The test pattern

Copy `tests/test_collector_TEMPLATE.py`. The shape: build a minimal fixture in `tmp_path`
(artifact mode) or a fake tool caller (connected mode), run `collect()` directly — the
decorator returns your function unchanged — and assert on `stats`, finding titles/severities/
dimensions, and that messy input yields findings instead of exceptions. Keep fixtures free of
secret-shaped literals; assemble them at runtime (see `tests/conftest.py::planted_secret_line`
and SECURITY.md).

### Checklist

- [ ] Copied TEMPLATE.py; `@collector` metadata filled in; signature matches `inputs`
- [ ] Reuse checklist run (connected mode: which MCP server, and is it the shared one?)
- [ ] Findings deterministic; evidence type honest; no raise on messy input
- [ ] Tests copied and adapted; `uv run pytest tests/ -q` green
- [ ] Dimension/offering ids registered (profile or baseline)
- [ ] `qba assay list-collectors` shows your collector with sensible descriptions

## Where collectors live

Placeholder pending decision **[A6]**: write client-specific collectors in the client's
engagement repo (isolation; the client's IP stays theirs). When one generalizes, promote it
into this repo — target `collectors/contrib/` — with client identifiers removed and fixtures
anonymized. The promotion bar and the `contrib/` split are not final; check ASSAY_PLAN.md's
open-decisions list before promoting anything.

## Tier 2 — core enhancements

A new acquisition mode, engine capability, or enforcement primitive is planned, additive work
— and if it is a *cross-cutting* enforcement primitive, it belongs in `harness/`, not here
(same one-way-dependency rule as everything else in the repo). Open a design conversation
before writing code.
