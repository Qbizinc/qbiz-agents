# Assay — Data & AI Discovery Assessment Framework

*Design doc & build plan. Status: Phase 1 scaffold built (2026-07-09); reframed from a
single-purpose pre-sales tool to an extensible discovery framework (2026-07-13); corrected
`mcp_aws` merge status after the branch stack landed on `master`, and Phase 2 framework core
built (2026-07-14) — the "Phase 1 delta" notes in the seams below are resolved history.
Recommendations prioritization designed and folded in (2026-08-07), **designed but not built**.
Owner: David Sevier.*

> ## ⚠ Review this plan before building against it
>
> **Nothing in the unbuilt sections below should be implemented until this document has had a
> full review.** Two specific reasons, both earned:
>
> 1. **The unresolved open decisions are load-bearing, not cosmetic.** `[A3]` (rubric
>    calibration) has been open since Phase 1 and now gates a second axis as well as the scores;
>    `[A5]` must close before the first connected collector ships; `[A8]`–`[A15]` gate
>    prioritization. Building against an open decision bakes a guess into code.
> 2. **The prioritization design was drafted four times, and the third draft contained a
>    disqualifying flaw that its author did not catch.** Two independent reviewers (Engineer and
>    Challenger personas, `personas/`) found that v3's default configuration would have shipped
>    ~900 lines to reproduce a plain severity sort, plus an arithmetic error in the band
>    threshold. Both were verified before the redesign. **The current text is v4 and has not
>    been reviewed by anyone.** The older sections of this plan have never had that treatment at
>    all.
>
> Recommended: the three-role pattern in `personas/AGENTS.md` — Engineer and Challenger
> independently and blind to each other, Architect reconciling — run against the whole document,
> not only the newest section.
>
> The full derivation behind the prioritization section — all four drafts, both review rounds, and
> the transcribed prior-art methodology — is preserved at
> `personas/artifacts/assay-work-20260807/`. **Read the two round-2 reviews there before
> reopening any of its design decisions**; they carry the verified arithmetic for why v3 was
> abandoned and why an axis registry was cut, and re-deriving that is expensive.

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

### The RAG store's role across the framework

The `rag` MCP is the shared, queryable store the reuse rule points connected/persistent needs
at (`mcp/mcp_rag/`, local `fastembed` embeddings — no key, no `[D3]` dependency; consumable
either as an MCP toolset or the library-embed pattern the incident-memory skill uses). It earns
its place in Assay only where the input is *genuinely unstructured*. Three uses, in value order:

1. **Interview / document-evidence collector (Phase 4) — the strongest new fit.** Interview
   mode's whole point is the dimensions with no parser: governance *process*, retention policy,
   siloing, ownership culture. Much of the evidence for those already exists as client documents
   — policy PDFs, runbooks, data dictionaries, Confluence/wiki exports, org charts — just not in
   a form a deterministic collector can read. A RAG-backed collector `ingest`s the client-shared
   docs, then runs targeted `search` queries ("documented data-retention policy?", "incident
   escalation runbook?", "named data owner per domain?") and emits `Finding`s with evidence type
   **`system-of-record`** where a document backs the answer — an evidence-quality upgrade over
   the `attestation` a bare interview yields. This is the mechanism that lets the full tier
   assess its softest dimensions honestly instead of vibes-scoring them, and it lands as a
   Tier-1 collector (`requires_mcp: rag`).
2. **Cross-engagement precedent / calibration corpus (Phase 5).** Index every past Assay report
   (findings, scores, offering roadmap) into RAG; at assessment time, `search` for comparable
   estates to surface what similar clients scored and which remediation followed. The
   `list_sources` ledger *is* the accumulating benchmark corpus — the concrete substrate for the
   long-open **`[A3]`** score-calibration item (real prior engagements to anchor bands against)
   and the raw material for **`[A2]`** benchmarking, once its consent bar is settled.
3. **Re-assessment trend line (Phase 5, already planned).** Index prior runs of the *same*
   client keyed by engagement; on re-run the narrator recalls them to report score deltas and
   recurring findings — the retainer story. (Already a Phase 5 bullet; #1 and #2 make it cheaper
   by the time it's built.)

**The boundary that keeps this honest:** RAG never touches the artifact collectors. `manifest.json`,
DAG ASTs, and the credential scan are deterministic, zero-token, parsing-only *by design* —
their findings are facts, not semantic-search matches, and routing them through RAG would break
the deterministic-first rule and the "findings the narrator can't alter" guarantee. RAG belongs
only where the alternative is a human reading unstructured prose. **Watch the tags gotcha** the
incident-memory dogfooding surfaced: `rag search(tags=...)` is OR / any-of, not AND, so scope
each client's corpus by a *unique engagement tag alone* — a shared `assay` tag would bleed one
client's documents into another's recall.

## Recommendations prioritization

*Designed 2026-08-07, **not built**. Gated on `[A8]`–`[A15]` and on the plan-wide review above.*

Consultants have historically ranked engagement recommendations into P0–P3. Assay ships half of
that today: the report groups findings by offering and ranks the groups by summed severity
deduction — one axis, no bands. `ASSAY_PLAN` calls that section a proposal skeleton, and a
skeleton with one axis cannot be sequenced or scoped. This section adds the second axis.

### Axis sets

Every recommendation gets two coordinates, and **which pair to use is a consultant call** that
depends on the client and on what we were engaged to evaluate. Two ship:

| Set | Y (derived) | X | Grain | Combination |
| --- | --- | --- | --- | --- |
| `urgent_strategic` *(default)* | Urgency — from severity | Strategic value — from the client-set dimension weight, overridable per row | recommendation | power-mean contour |
| `impact_effort` | Impact — `severity_weight × dimension_weight` | Effort — band, human-supplied | workstream | quadrants |

These are **two constants in code, not a config registry.** A registry was designed and cut: the
derive functions are code either way, so "add your own axis set" was never a config-only move, and
the two sets differ by a cost flag and two labels. What a profile retunes — shape, weights, band
thresholds, effort defaults, default set — is flat config.

### Where the human input goes

**Strategic value is a property of a business theme, not of a task.** Asking a consultant to type a
value on each of thirteen findings invents thirteen opinions where the client has one. So it is
captured once, at dimension grain, via `rubric.dimensions[].weight` — a field the framework already
parses, already merges, and already advertises as *the* Tier-0 client-tuning move. Each row's
strategic coordinate is then derived, and a consultant may **override an individual row** in a
workshop; the override is provenance-tagged.

Because every row always has a derived value, there is no empty state — which matters more than it
sounds. An earlier design left the axis unset by default and degraded to the derived axis, which
made *leaving a field blank* score better than answering it honestly, and collapsed the whole output
back onto severity.

The client ranks in their own vocabulary via a challenge→dimension map (Tier-0 config), so the
scoping conversation is about business themes rather than our rubric's internal ids:

```yaml
challenges:
  data_confidence:      { dimensions: [data_quality, documentation] }
  development_velocity: { dimensions: [operations] }
  cost_efficiency:      { dimensions: [cost] }
  security_risk:        { dimensions: [governance, ai_governance] }
```

### Provenance on every axis value

Same discipline `EvidenceType` applies to findings, applied to coordinates. Findings are
deterministic facts the narrator may explain but never alter; an axis value that a human or an agent
supplied must say so, or model output launders into the facts column.

```python
class AxisSource(str, Enum):
    DERIVED    = "derived"       # computed from findings + rubric
    CONSULTANT = "consultant"    # typed by a human in the workshop
    PROPOSED   = "proposed"      # agent-suggested, unreviewed — never auto-accepted
    DEFAULT    = "default"       # config default (effort bands)
    MEASURED   = "measured"      # RESERVED — no data path exists; see below
```

`MEASURED` is reserved and deliberately unimplemented: per-finding counts live interpolated inside
title f-strings and in `CollectorResult.stats` under ad-hoc per-collector keys with no link back to
the finding. Building that join would be exactly the framework bug this document's core design rule
names. The member exists so stored matrices stay forward-compatible.

### Combination — contours for value×value, quadrants for value×cost

Normalize each axis against a **declared absolute maximum, never the observed set.** Set-relative
normalization is unstable across re-runs and, worse, promotes the next-worst item as soon as a
client fixes something. Absolute maxima are also what make scores comparable across engagements,
which `[A8]` calibration needs.

Two **value** axes combine by power mean, `score = (Σ wᵢ·xᵢ^p / Σ wᵢ)^(1/p)`:

- `p = 1` → weighted sum → straight diagonal boundaries.
- `p = 2.409` → exact crossover: a lone maximum on one axis reaches the P0 threshold unaided.
- `p = 3.0` → shipped default. Mostly-flat-then-plunging contours, matching prior engagement
  methodology.
- `p → ∞` → `max()`, a square corner. Explicitly not the target shape.

A **cost** axis does not get a contour. "Extreme on one axis is sufficient" is correct for two value
axes and produces nonsense against a cost — a zero-impact trivial task outranking an important hard
one. `impact_effort` therefore uses explicit quadrant thresholds with `impact / effort` ordering
inside each quadrant.

`priority_floor: {critical: P0}` is retained: redundant at the shipped shape, load-bearing under
`weighted_sum` and in the `weight: 0` case, where a dimension override can zero a CRITICAL's derived
coordinate.

### Stable identity — a prerequisite, not a detail

Overrides and workshop notes are hand-typed data that a re-run must never destroy, which requires
ids stable across runs. Finding-derived ids are not: titles embed live counts, severities are
computed from thresholds, the collector name is discarded when findings are flattened, and the
natural composite key collides between two of the dbt collector's own findings.

**This needs an explicit `key` field on `Finding`** — collector-authored, stable, unique per
collector (`"dbt.test_coverage"`). One field, four collectors, their tests. There is no cheaper fix
that survives a re-run, and it must land *before* anything else here, because everything joins on it.

`sync` is correspondingly a merge and never an overwrite: four arms (unchanged / new / disappeared /
changed-but-matched), a `status` field so a finding that vanished because the client *fixed* it is
recorded rather than deleted, atomic write, and a drop-guard refusing to orphan more than N rows
without `--force`. This is the highest-risk code in the feature; its merge tests are an explicit
acceptance criterion.

### Delivery

Internal-only for now — a consultant may show the matrix to a client after cleaning it up, and a
polished client-facing render is a later enhancement. That constraint is enforced by the renderer
refusing to embed prioritization output unless explicitly flagged, rather than left as a promise;
`[A4]` graduates read-only from principle to mechanism, and this should not hold itself to a lower
bar.

The edited artifact and the consumed artifact are the same YAML file. Re-banding is a first-class
CLI path (`--weight`, `--shape`) because the prior-art methodology is explicit that axes get
renegotiated with the client in the room — this is a facilitation instrument, not only a batch
report generator.

```
qba assay prioritize init   <profile.yaml> [--axes impact_effort] --out items.yaml
qba assay prioritize sync   <profile.yaml> items.yaml
qba assay prioritize render items.yaml [--weight strategic=1.5] [--shape 4] --out matrix.md
```

The agentic half follows the `Narrator` seam exactly: an `AxisEstimator` Protocol with a zero-cost
deterministic fallback, run under the harness at the same call site, `Tier.MID` ceiling via
`model_policy`, output tagged `PROPOSED`, never overwriting a `CONSULTANT` value, and written as a
proposal the consultant diffs rather than a direct write. Its best job is proposing **dimension
weights** from the client's own written strategy — grounded in the documents the Phase 4
document-evidence collector already plans to ingest. Six weights sourced from a client's own charter
is citable; thirteen per-row guesses are not. Sequence it after that collector.

**Related fix, shippable independently:** the roadmap ranks offering groups by summed severity
deduction *without* dimension weight, while `overall_score` applies it. Invisible while every
baseline weight is `1.0`, but a profile that reweights — the advertised Tier-0 move — makes the
scorecard and the roadmap rank by different arithmetic in one document. Prioritization raises the
stakes, since dimension weight now drives the strategic axis. Tracked as `[A11]`; it is a design
question, not merely a bug, because offering groups span dimensions.

**Sizing:** ~900–1200 lines including tests. Stated with its history: this was estimated at ~500–700
and ~800–1000 in earlier drafts, and independently costed at roughly double the second figure. Treat
900–1200 as a floor. If it proves over-built, the cheapest thing that could work is to render the
grid and let the room place the items, with no computed priority at all — closer to the prior-art
methodology than anything designed here, and roughly a fifth of the code.

## Build phases

- **Phase 1 — scaffold (DONE 2026-07-09):** the pulse-tier pipeline end to end: three artifact
  collectors (dbt manifest, Airflow AST scan, repo AI-usage scan), six-dimension rubric,
  narrator Protocol with rule-based fallback, harness-governed engine, markdown report,
  narrated demo (`demo/assess_acme.py`), tests.
- **Phase 2 — framework core (genericize before deepening) — DONE 2026-07-14:** everything
  in "The seams" that Phase 1 lacked, *before* any new collector was written, so every later
  collector lands on the plugin API instead of deepening the hardcoding. Delivered as listed
  below (config registries in `config/qbiz_baseline.yaml` + `config.py`; `@collector`
  registry with acquisition modes and `requires_mcp`; evidence typing on `Finding`;
  engagement profiles + `qba` CLI in `profile.py`/`cli.py`; `docs/EXTENDING.md` +
  `collectors/TEMPLATE.py` + `tests/test_collector_TEMPLATE.py`). The acceptance test landed
  as the real thing: `collectors/cloud_posture.py`, a connected-mode collector for the
  out-of-list `cloud_posture` dimension calling the shared `aws` MCP server through an
  injected tool caller (live MCP transport binding is Phase 3). [A3] deferred: baseline
  weights/bands are the Phase 1 values, now in config, still uncalibrated. [A6] deferred:
  documented as a placeholder in EXTENDING.md.
  - Dimension/rubric/offering registries + config loaders; Qbiz baseline shipped as the
    default config; overall score becomes dimension-weighted (weights in config).
  - `Collector` Protocol, registration decorator, discovery (`list-collectors`).
  - Engagement profile loader; `qba assay run <profile>` CLI.
  - Engine/report refactored to iterate registries; the three Phase 1 collectors migrated.
  - **The extension documentation:** `docs/EXTENDING.md` + collector template + test scaffold.
  - **Acceptance test:** the cloud-posture worked example (or equivalent out-of-list
    domain) implemented at Tier-1 effort by following the docs alone.
- **Phase 2.5 — recommendations prioritization (DESIGNED, NOT BUILT):** the second axis on the
  roadmap, per [Recommendations prioritization](#recommendations-prioritization). Slots before
  Phase 3 because nothing in it is blocked by connected collectors, and because it upgrades the
  section that is already the commercial payload of the deliverable. **Gated on `[A8]`–`[A15]` and
  on the plan-wide review — do not start against open decisions.** In dependency order:
  - **`Finding.key`** — explicit collector-authored stable id, plus the four collectors and their
    tests. Everything else joins on it; it lands first or not at all.
  - Flat `prioritization:` config section, its merge block, and validators. Note the existing
    override machinery is bespoke per-section, so this is a hand-written merge arm, not free reuse.
  - `prioritize.py`: `Item`, `AxisSource`, the two `AxisSet` constants, power-mean and quadrant
    combination, banding.
  - `sync` with all four arms, `status`, atomic write, and drop-guard. Merge tests are an
    acceptance criterion, not a nicety.
  - Challenge→dimension map — Tier 0, config only.
  - `qba assay prioritize init / sync / render`, including the workshop re-banding overrides.
  - `AxisEstimator` Protocol + deterministic `DefaultEstimator` (no key, no `[D3]` dependency).
  - The LLM estimator for dimension weights is **not** here — it belongs after Phase 4's
    document-evidence collector, which is what makes its proposals citable.
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
  - **Document-evidence collector** (RAG-backed, `requires_mcp: rag`): ingest client-shared
    unstructured docs (policies, runbooks, data dictionaries, wiki exports) and query them to
    back the same soft dimensions with `system-of-record` evidence instead of bare attestation.
    See [The RAG store's role across the framework](#the-rag-stores-role-across-the-framework),
    use #1 — this is the reuse rule applied: consume the `rag` MCP, don't grow an Assay store.
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
  - **Cross-engagement precedent corpus** (RAG MCP): index past reports so an assessment can
    recall comparable estates — the concrete substrate for `[A3]` calibration (real engagements
    to anchor bands against) and the raw material for the benchmark below. See
    [The RAG store's role across the framework](#the-rag-stores-role-across-the-framework), use #2.
  - Anonymized cross-client benchmark ("bottom quartile for test coverage") — **needs the
    `[A2]` data-ethics/consent decision before any pooling.**

## Open decisions

**`[A8]`–`[A15]` gate Phase 2.5 and must be closed before it is built.** They are not deferred
polish: each one bakes a guess into code if built around rather than decided.

- **[A1] Delivery form:** consultant-run CLI (current), client-runnable self-serve, or both?
  Self-serve is a lead magnet but exposes the rubric to gaming. The pulse/full split sharpens
  this: self-serve only ever makes sense for the pulse tier.
- **[A2] Benchmark pooling:** consent model and anonymization bar for cross-client comparisons.
- **[A3] Rubric weights:** severity weights (40/25/10/4/0) and bands are sensible defaults;
  calibrate against a few real engagements before anyone quotes a score externally. Phase 2
  moves them from code to config, which is the enforcement half of this decision; calibration
  remains open. The Phase 5 RAG precedent corpus (past reports indexed for recall) is the
  intended substrate for doing this against real engagements rather than by hand — see
  [The RAG store's role across the framework](#the-rag-stores-role-across-the-framework), use #2.
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

### Prioritization (Phase 2.5)

- **[A8] Axis calibration.** Band thresholds, the contour shape, and effort band defaults are
  uncalibrated guesses — `[A3]`'s problem on new axes, and it now affects a *ranking* handed to a
  client rather than only a score. Absolute normalization is what makes cross-engagement
  calibration possible later; the Phase 5 precedent corpus is the intended substrate for both.
  Do not quote a priority ranking externally until this closes.
- **[A10] Sync conflict policy.** When a re-run's derived strategic value contradicts a stored
  `CONSULTANT` override: keep silently, keep and flag, or prompt? Proposed: keep and flag in the
  render. Decide before `sync` is written — this is its semantics, not a detail layered on top.
- **[A11] Roadmap ranking weight.** Should offering-group ranking apply dimension weight, given
  that groups span dimensions? Genuinely a design question, not just the bug fix it resembles.
  Consequential now that dimension weight drives the strategic axis: whichever way it goes, the
  roadmap and the matrix must agree inside one document. Shippable independently of everything
  else in Phase 2.5.
- **[A13] Prior-art provenance.** The Urgent × Strategic methodology comes from a previous
  engagement's slide. Its *curvature* is confirmed against the original; whether the methodology
  was actually used, and whether it worked, is not. "Built for X" does not mean "used for X" —
  ask whoever ran that engagement. Gates `default_axis_set` only, nothing else.
- **[A14] A third axis set, `impact_confidence`.** Would be the only fully-derivable pair, and
  provenance is a real differentiator — competitors claim an effort column; none can show where
  a number came from. Cheap *only* if `EvidenceType` (three labels, no numbers) gets a value map.
  Deferred, not rejected.
- **[A15] Override granularity.** Strategic value is overridable per row. Should *urgency* be
  too? Proposed: **no.** Severity is the deterministic spine of the assessment, and a
  hand-editable severity is precisely where the "findings are facts, not opinions" property
  breaks — the one property the tool is sold on.

*(`[A9]` — HITL placement for estimate acceptance — resolved during design: a local CLI diff for
v1. The harness's Component 8 is `async` while Assay is synchronous throughout, and no
`ApprovalTransport` implementation exists in-repo; revisit when the output goes client-facing.
`[A12]` — a warning when a workstream carries too many findings — was superseded when
recommendation grain became the default.)*

## Presentation tie-in (internal deck, 2026-07)

Assay is the "where we go from here" slide made concrete: the landscape shifted from
generation to verification/judgment/accountability — and Assay is literally a product that
sells judgment (scored findings), verification (evidence-backed, reproducible), and
accountability (audit trail in the deliverable). The framework reframe adds the second-order
pitch: the discovery phase of every engagement gets faster each time we run one, because
every engagement leaves a collector behind. One slide, one demo run, one report page.
