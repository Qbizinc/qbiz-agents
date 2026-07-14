# Assay — Data & AI Discovery Assessment Framework

*Design doc & build plan. Status: Phase 1 scaffold built (2026-07-09); reframed from a
single-purpose pre-sales tool to an extensible discovery framework (2026-07-13); corrected
`mcp_aws` merge status after the branch stack landed on `master` (2026-07-14). Owner:
David Sevier.*

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

And beyond what artifacts can show: ungoverned warehouse and AI spend nobody can attribute,
security posture nobody has reviewed since setup, and organizational siloing — three teams
maintaining three copies of the same customer table because none of them trusts the others'.

**Assay is a governed assessment framework that scans a client's data estate and turns those
problems into a scored, evidence-backed readiness report** — with a remediation roadmap that
maps each gap to the Qbiz engagement that retires it. It is the discovery phase of an
engagement, productized: the same framework runs as a one-hour pre-sales pulse check or as
the evidence backbone of a multi-week discovery.

## Why this tool (vs. the other candidates)

Ranked against the alternatives from the AI-consulting positioning work (migration agent, dbt
generator, data-quality triage, NL-to-analytics):

1. **It is the direct answer to the positioning goal** — "companies trying to learn how to use
   AI well, both effectiveness and efficiency." An assessment *is* that conversation, productized.
2. **It's a pre-sales lever.** Run the pulse tier in discovery from three artifacts a prospect
   can share in an hour. The report's roadmap is a proposal skeleton: every finding names the
   offering that fixes it.
3. **It's the meta-demo of the harness.** The assessment itself runs under `qbiz_harness` —
   cost-capped, loop-bounded, redundancy-guarded, audited — and the report's final section
   discloses the numbers. "The report you're holding was produced by a governed agent" is the
   pitch, delivered by the deliverable.
4. **It's unblocked.** Collectors and scoring are deterministic (no LLM, no key, no `[D3]`
   provider decision). The only LLM stage — narrative — sits behind a Protocol with a
   deterministic fallback, so the whole thing ships and demos today.
5. **It compounds.** Every heuristic a consultant learns on an engagement becomes a collector;
   every engagement makes the next assessment sharper. The framework reframe is this point
   taken seriously: extension has to be so cheap that compounding actually happens.

The migration agent remains the bigger *revenue* play, but it needs a legacy corpus to demo
and a much larger build. Assay is the wedge that gets us into that conversation.

## Delivery modes

The original build treated "one hour before an engagement" as *the* product. It is now one
tier of two:

| Mode | When | Inputs | Credentials | Duration |
| --- | --- | --- | --- | --- |
| **Pulse check** | Pre-sales, discovery day one, client self-run | Shareable artifacts only (manifest.json, DAG folder, repo read access) | **None — hard constraint** | ~1 hour |
| **Full assessment** | Engagement discovery phase | Artifacts + read-only connections (warehouse, billing, IAM) + structured interviews | Read-only, per-system sign-off `[A5]` | Days–weeks, resumable |

The pulse tier's zero-credential property is load-bearing: it's what makes it a lead magnet a
prospect will actually agree to, and it stays a hard constraint on that tier forever. The full
tier is where Data Governance depth, DB Spend, AI Spend, Security posture, and Siloing live —
dimensions that need connections or conversations, not just files.

## Architecture

**Deterministic-first, LLM-last.** That IS the effectiveness-and-efficiency story, embodied:

```
 inputs                    stage                     cost      trust
 ──────────                ─────────────────────    ─────     ─────────────────────────
 artifacts          ┌──►   collectors (parsing,     free/     facts — never LLM output
 read-only conns    │        queries, interviews)   metered
 questionnaires     │      rubric (arithmetic)      free      reproducible scores
                    │      narrator (LLM)           metered   explains, cannot alter facts
                    │      report (markdown)        free      roadmap → Qbiz offerings
                    └──    all of it under qbiz_harness: CostGovernor, LoopGuard, AuditLog
```

### The core design rule

**Core pieces iterate registries, never enums.** Anything the framework "knows about" —
dimensions, collectors, offerings, evidence types — is data it discovers at runtime, not code
it was compiled with. The engine, rubric, and report are generic machinery; every
domain-specific fact lives in a registry entry or a config file. If adding an assessment
domain requires editing `engine.py`, `rubric.py`, or `report.py`, that is a framework bug.

### The seams (target state; Phase 1 deltas noted)

- **Dimension & rubric registry** — dimensions, titles, severity weights, score bands, and
  per-dimension weighting for the overall score, all loaded from config. Qbiz ships a baseline
  rubric (`rubric/qbiz_baseline.yaml`); an engagement profile can override any of it, honoring
  the standing principle that a client's own standards beat the Qbiz default. *Phase 1 delta:
  today `Dimension` is a closed enum and weights/bands are constants in `findings.py` /
  `rubric.py`.*
- **Offering catalog** — the remediation→engagement mapping as config, so the roadmap section
  works for any practice area without touching collector code. *Phase 1 delta: five hardcoded
  string constants.*
- **Collector contract & registry** — a `Collector` Protocol with declared metadata: name, the
  dimension ids it can assess, its **acquisition mode** (see below), the file paths /
  questionnaire ids it needs, and — for connected mode — the **`requires_mcp` server(s)** it
  calls (same field name and purpose as a skill's `requires_mcp`; see [Reuse over
  duplication](#reuse-over-duplication-check-for-a-shared-tool-first)). Collectors register via
  a decorator; `qba assay list-collectors` shows what is available and what each needs — files,
  questionnaires, *or MCP connections* — so a consultant can see at a glance what can be
  assessed given what a client can share or grant. *Phase 1 delta: collectors are bare functions
  wired by hand at the call site; no MCP-backed collector exists yet.*
- **Engagement profile** — the per-client entry point: one YAML file naming the client, the
  delivery mode, the enabled collectors and their inputs, rubric/offering overrides, and
  harness limits. Writing one is the whole "plug into a client's tech stack" step for any
  stack the collector library already covers. *Phase 1 delta: doesn't exist; callers compose
  `partial()`s in Python.*
- **Acquisition modes** — three, and a collector declares exactly one:
  - **artifact** — offline parsing of files the client shared. Zero credentials, zero network.
    The only mode Phase 1 has; the only mode the pulse tier allows.
  - **connected** — read-only queries against live client systems (warehouse query history,
    billing exports, IAM/grants). This is where the harness stops being a demo and becomes
    load-bearing: per-run query action caps, read-only enforcement, HITL sign-off before first
    touch `[A5]`, every query in the audit trail. A client grants access *because* the
    governance is demonstrable.
  - **interview** — structured questionnaires whose answers flow through the same `Finding`
    pipeline. This is how non-scannable dimensions (Siloing, governance *process*, ownership
    culture) get assessed honestly instead of being skipped or vibes-scored.
- **Evidence typing** — every `Finding` carries an evidence type: `artifact` (we parsed it),
  `system-of-record` (we queried it), or `attestation` (someone told us). The report
  distinguishes them; a score built on attestations says so. *Phase 1 delta: field doesn't
  exist yet.*
- **Findings, engine, narrator, report** — the Phase 1 pipeline survives intact: `Finding` as
  the deterministic vocabulary the narrator may explain but never alter; the engine as the
  harness call site (governed degradation — a capped run finishes on the rule-based narrator,
  never half-fails); the report ending with "How this assessment was produced" and the audit
  numbers.

Dependency direction honors the repo rule: `qbiz_assay` imports `qbiz_harness`; nothing
imports back.

## The extension model

The point of the framework. Extension effort comes in three tiers, and the design goal is
that client-stack variation lands as low on this ladder as possible — but **"we have to write
code" is the expected case for a genuinely new check, not a failure**. Our consultants are
Python-proficient; the framework's job is to make the code they write small, obvious, and
impossible to wire up wrong.

| Tier | What changes | Examples | Effort |
| --- | --- | --- | --- |
| **0 — config only** | Engagement profile / rubric YAML | Enable/disable collectors, retune weights and bands, rename a dimension for client vocabulary, remap offerings | Minutes |
| **1 — one new collector** | One Python file implementing the Protocol + config entries | Any new check against a stack the modes already support: a Dagster collector, a Looker metadata scan, a Fivetran connector audit | Target: **under a day, most in an hour or two** |
| **2 — core enhancement** | A new acquisition mode or engine capability | The first interview-mode plumbing; a streaming/log-based mode if one is ever needed | Rare, additive, planned work |

Tier 1 is the one that must be *quick, easy, and well documented*, because it's where
compounding lives. Deliverables that make it so (Phase 2): a `collectors/TEMPLATE.py` with
the Protocol spelled out, a `docs/EXTENDING.md` authoring guide (contract, registration, test
pattern, worked example), and a test scaffold so a new collector's tests are copy-adapt.

### Reuse over duplication — check for a shared tool first

**Standing repo-wide rule, not just an Assay one:** `qbiz-agents` is one repo of composable
tools *on purpose* — the harness, the MCP servers, the RAG store, Assay — so that capability
built for one consumer is available to every other one. Before writing collector code that
talks to an external system, ask, in order:

1. **Does an MCP server for this system already exist in `mcp/`?** If yes, the collector is a
   thin caller of it — a Tier-1 collector, same as any artifact collector, just with a
   `requires_mcp` entry instead of a file path.
2. **Is there an MCP server for it in flight but unmerged?** Check open branches before
   starting — coordinate to land the collector against the real server rather than a private
   stub.
3. **Does no server exist, and is the capability inherently generic** (any future agent might
   want to query this kind of system, not just Assay)? **Build `mcp/mcp_<name>/` first**, then
   write the collector on top of it. This is genuinely more work than writing the query code
   inline in `qbiz_assay` — do it anyway. A capability that only Assay can reach is a
   duplication liability the moment a second consumer needs it; a capability with an MCP
   server behind it is available to every agent in this repo for free.
4. Only write the integration directly inside `qbiz_assay` if it is **genuinely
   Assay-specific** — parsing logic over an artifact format, not a connection to a live
   system. This should be rare; artifact collectors are the common case here, not connected
   ones.

The same question applies one level up, past collectors: a new cross-cutting enforcement
primitive belongs in `harness/`, not duplicated as Assay-only governance code; a persistent,
queryable store belongs behind the `rag` MCP (Phase 5's re-assessment trend line already does
this correctly — see Build phases). If in doubt, the direction of the dependency should be
"Assay imports/calls the shared tool," never "Assay grows its own copy of what the shared tool
does." This is the same one-way-dependency discipline `qbiz_harness` established, applied to
every tool in the repo, not just the harness.

**What this changes concretely in the phases below:** the DB Spend collector is a caller of
the existing `snowflake` MCP; the Security collector is a caller of `mcp_aws` (already built
**and merged to `master`** — no branch to land, just a collector to write); AI Spend has no
home yet, so it's a candidate *new* MCP server, not Assay code. See Phase 3.

### Worked example: a network security / cloud posture check

Illustrates the rule above with something *already real*, not hypothetical — and, as of
2026-07-14, real in a stronger sense than first written: `mcp_aws` merged to `master` on
2026-07-07 (PR #7), before this framework reframe even started. A `network_security` (or
broader `cloud_posture`) dimension is still not on the collector list, but the tool it needs
is sitting there already:

1. **Check for a shared tool first** (the step above) — `mcp_aws` (server name `aws`,
   `mcp/mcp_aws/`, merged to `master`) is a read-only AWS MCP server already exposing
   `iam_list_roles`, `iam_get_policy`, `s3_get_bucket_policy`, `s3_get_bucket_encryption`,
   `redshift_describe_clusters`, and more, via an assumed least-privilege IAM role. That
   covers most of a first cloud-posture pass (public bucket exposure, over-broad IAM policies,
   unencrypted storage) with **zero new external integration code and zero merge work** — the
   `skills/aws-readonly-explorer/` skill already documents how an agent calls it, and is worth
   reading before writing the collector even though it's a different consumer (agent vs.
   collector) of the same server.
2. **Dimension** — add `cloud_posture` (title, weights, band thresholds) to the rubric
   config. *Tier 0.*
3. **Collector** — write `cloud_posture.py`: a connected-mode collector that calls the `aws`
   MCP's tools, turns specific findings (a public bucket, an IAM policy with
   `"Resource": "*"`, unencrypted storage) into `Finding`s tagged `cloud_posture` with evidence
   type `system-of-record`, declares `requires_mcp: [aws]`, registers itself. One file, no new
   credentials to design — `mcp_aws`'s STS role-assumption pattern already solves that. *Tier
   1, and unblocked — nothing to land first.*
4. **Offering** — map remediations to a "Cloud Security Review" entry in the offering
   catalog. *Tier 0.*
5. **The gap that's left:** `mcp_aws` doesn't (yet) expose IAM password-policy, access-key
   age, or MFA-enforcement checks — classic posture signals. Per the rule above, that's an
   argument to **extend `mcp_aws`** with a couple more read-only IAM calls, not to reach for
   `boto3` inside `qbiz_assay`.

Engine, rubric, and report never change — they iterate the registries. If step 3 turns out to
need edits to core files, or to need cloud API code Assay doesn't already have a shared tool
for, that's a signal to stop and go build/extend the shared tool (step 1/5), not to route
around it. **This example is the acceptance test for Phase 2**: the phase isn't done until an
out-of-list domain lands at documented Tier-1 effort, reusing an existing or newly-extended
shared tool rather than duplicating it.

### Where client-specific collectors live `[A6]`

Default: write them in the client engagement repo (isolation, client IP stays theirs),
promote to this repo's `collectors/contrib/` when generalized. The promotion step is the
compounding flywheel — needs a real decision on the default and the generalization bar.

## Build phases

- **Phase 1 — scaffold (DONE 2026-07-09):** the pulse-tier pipeline end to end: three artifact
  collectors (dbt manifest, Airflow AST scan, repo AI-usage scan), six-dimension rubric,
  narrator Protocol with rule-based fallback, harness-governed engine, markdown report,
  narrated demo (`demo/assess_acme.py`), tests.
- **Phase 2 — framework core (genericize before deepening):** everything in "The seams" that
  Phase 1 lacks, *before* any new collector is written, so every later collector lands on the
  plugin API instead of deepening the hardcoding:
  - Dimension/rubric/offering registries + config loaders; Qbiz baseline shipped as the
    default config; overall score becomes dimension-weighted (weights in config).
  - `Collector` Protocol, registration decorator, discovery (`list-collectors`).
  - Engagement profile loader; `qba assay run <profile>` CLI.
  - Engine/report refactored to iterate registries; the three Phase 1 collectors migrated.
  - **The extension documentation:** `docs/EXTENDING.md` + collector template + test scaffold.
  - **Acceptance test:** the cloud-posture worked example (or equivalent out-of-list
    domain) implemented at Tier-1 effort by following the docs alone.
- **Phase 3 — depth via connected collectors:** the full-assessment tier's scanning half.
  Every bullet here starts with the [reuse check](#reuse-over-duplication-check-for-a-shared-tool-first)
  — named explicitly per item because this is the phase where it matters most:
  - **DB Spend** (warehouse query-history hotspots, attribution gaps, idle warehouses) → a
    thin collector calling the existing `snowflake` MCP server (`mcp/mcp_snowflake/` — a
    managed read-only server; its exposed tool list needs squaring up with what this collector
    requires before it can run `QUERY_HISTORY`-style reads — coordinate with whoever owns that
    server rather than standing up a parallel Snowflake client). A BigQuery equivalent needs
    its own MCP server the same way, when a BigQuery client shows up.
  - **Security / cloud posture** — a collector calling `mcp_aws` (server name `aws`: read-only
    IAM/S3/Redshift via an assumed role, merged to `master` since 2026-07-07 — see the worked
    example above). No merge prerequisite; this is a Tier-1 collector away from shipping.
    GCP/Azure equivalents don't exist yet; treat each as its own future MCP server, not a
    bolt-on to `mcp_aws`.
  - **AI Spend** (provider usage/billing attribution, corroborated against the Phase 1 repo
    scan) — **no shared tool exists for this anywhere in the repo.** Per the reuse rule, this
    is a candidate new `mcp/mcp_ai_billing/` (or per-provider) server, built *before* the
    collector, not provider SDK calls written directly into `qbiz_assay`. Track as **`[A7]`**
    below — it's new build, not a decision, but it's sized like one.
  - Deeper **Data Governance**: ownership coverage, catalog presence, retention signals —
    likely extends the existing `dbt` collector and/or a catalog tool if one exists for the
    client, rather than a new system integration.
  - dbt Cloud / Fusion artifact ingestion (today assumes a Core-style manifest) — artifact
    mode, no new shared tool needed.
  - Connected-mode harness posture: per-system HITL sign-off before first touch, query action
    caps, full query audit `[A5]` — this is `qbiz_harness` machinery the engine already has;
    connected collectors consume it, they don't reimplement it.
  - LLM narrator behind the existing Protocol (pydantic-ai, consistent with the incident DAG;
    inherits the open `[D3]` provider decision — nothing else here blocks on it).
- **Phase 4 — full-assessment workflow:** the engagement-shaped half:
  - Interview mode: questionnaire schema, answer capture, attestation findings — unlocks
    **Siloing** (org structure, duplicated pipelines, trust boundaries) and governance-process
    dimensions.
  - Evidence typing surfaced throughout the report; findings register + per-dimension workbook
    as the full-tier report alongside the pulse-tier markdown.
  - Resumable multi-day engagement state (an assessment is now a directory, not a run).
- **Phase 5 — the compounding layer:** already modeled correctly on the reuse rule — both
  bullets call an existing shared tool instead of growing an Assay-only equivalent; keep it
  that way as they're built out:
  - **HITL gate on external delivery** (harness Component 8 via Slack MCP): a human approves
    before a report leaves the building.
  - **Re-assessment trend line** (RAG MCP as the store, same library-embed pattern as the
    incident memory skill): re-run each quarter, show score deltas — turns a one-shot
    assessment into a retainer.
  - Anonymized cross-client benchmark ("bottom quartile for test coverage") — **needs the
    `[A2]` data-ethics/consent decision before any pooling.**

## Open decisions

- **[A1] Delivery form:** consultant-run CLI (current), client-runnable self-serve, or both?
  Self-serve is a lead magnet but exposes the rubric to gaming. The pulse/full split sharpens
  this: self-serve only ever makes sense for the pulse tier.
- **[A2] Benchmark pooling:** consent model and anonymization bar for cross-client comparisons.
- **[A3] Rubric weights:** severity weights (40/25/10/4/0) and bands are sensible defaults;
  calibrate against a few real engagements before anyone quotes a score externally. Phase 2
  moves them from code to config, which is the enforcement half of this decision; calibration
  remains open.
- **[A4] Scope creep guard:** collectors must stay read-only forever — in *every* acquisition
  mode. The moment Assay *fixes* things it competes with the engagements it's meant to sell,
  and its risk tier jumps. For connected mode this graduates from principle to mechanism:
  read-only credentials required, plus query-level enforcement where the platform allows it.
- **[A5] Connected-collector authorization boundary:** what "permission to look" means per
  system — explicit written client sign-off per connection, a HITL checkpoint before a
  connected collector's first query of a run, or both. Decide before the first connected
  collector ships in Phase 3.
- **[A6] Client-specific collector home:** engagement repo first, promote to `contrib/` when
  generalized (proposed above) — confirm the default and define the promotion bar (no client
  identifiers, fixtures anonymized, follows the template).
- **[A7] AI/provider billing MCP:** no shared tool exists yet for provider usage/spend data
  (OpenAI, Anthropic, etc. billing or usage APIs), and the reuse rule says the AI Spend
  collector shouldn't be the first place that logic lives. Decide scope (which providers,
  usage API vs. billing export vs. both) and build `mcp/mcp_ai_billing/` — or confirm this
  is small enough to fold into an existing server — before Phase 3's AI Spend bullet starts.

## Presentation tie-in (internal deck, 2026-07)

Assay is the "where we go from here" slide made concrete: the landscape shifted from
generation to verification/judgment/accountability — and Assay is literally a product that
sells judgment (scored findings), verification (evidence-backed, reproducible), and
accountability (audit trail in the deliverable). The framework reframe adds the second-order
pitch: the discovery phase of every engagement gets faster each time we run one, because
every engagement leaves a collector behind. One slide, one demo run, one report page.
