# Assay — Priority × Effort Matrix

*Draft plan **v2**, 2026-08-07. Author: Architect, after Engineer and Challenger review of v1
(`REVIEW_engineer.md`, `REVIEW_challenger.md`; v1 preserved at `PRIORITY_MATRIX_PLAN.v1.md`).
**Scratch — not the real plan.** Intended to fold into `assay/ASSAY_PLAN.md` after David's review.*

*Provenance markers: **[E]** = adopted from Engineer, **[C]** = from Challenger, **[E+C]** = both
found it independently, **[A]** = Architect ruling on disagreement or new.*

---

## 0. What changed from v1, and why

Both reviewers, working blind to each other, landed on the same fatal flaw. I verified it in the
code before ruling.

**In v1, per-finding effort was a lookup on our own offering catalog.** `Finding` carries no size,
count, or scope field, so `task.effort` reduced to a pure function of `finding.offering`. Over the
shipped demo (`demo/out/REPORT_acme.md`, 13 findings) that yields **two** distinct effort values
and **four** distinct impact values. Sorted, the 7th of 13 impacts is 25 with **six items sitting
exactly on the median** — so v1's median-split quadrants collapse to either an empty `quick_win`
or the two cheapest dbt findings, depending on `>` versus `>=`. The matrix carried no information
it didn't already have from the offering grouping `report.py` ships today. **[E+C], verified.**

Worse: both CRITICAL findings in the demo have **no `offering`** (verified,
`ai_usage.py:133-142`), so they hit `fallback: M` and would render as *"Rotate the credential now
— Medium, 3–5 days."* **[C], verified.**

**The ruling: change the grain, keep the matrix.** v1 estimated at the wrong unit. Effort is real
at the **workstream** level and fictional at the finding level — which is why v1's own §4.3 had to
invent `overhead`, why §8 sourced calibration from closed *engagements*, and why the defaults were
already keyed by offering. Estimating where the number is real fixes the axis, and it dissolves two
other problems for free (§4.2, §4.4).

I did **not** adopt Challenger's stronger form — replace the matrix with a phase plan. A
Priority×Effort matrix is what was asked for and what consultants already use; at workstream grain
it becomes a *better* matrix, not a worse phase plan. **[A]**

## 1. Why

Consultants have historically ranked engagement work on a Priority-vs-Effort matrix (P0/P1/P2).
Assay does half of this: `report.py` groups findings by offering and ranks groups by summed
severity deduction — risk-ordering on one axis. There is no effort axis anywhere in `qbiz_assay`.

`ASSAY_PLAN.md` calls the roadmap section "a proposal skeleton." A proposal skeleton with no effort
dimension cannot be scoped.

## 2. Settled decisions (David, 2026-08-07)

| # | Decision | Consequence |
| --- | --- | --- |
| D-1 | **Both use cases, phased.** Assay findings are v1's only target. Standalone task lists and agent-created Jira tickets are a future enhancement. | `Task` is adapter-fed, not `Finding`-shaped, so the later path is a second adapter. v1 ships one adapter. |
| D-2 | **Effort in bands**, not raw engineer-days. | T-shirt bands with a day range shown; numeric midpoints for axis math only, never printed. |
| D-3 | **Internal-only for v1.** A consultant may show it to a client after cleaning it up. Polished client-facing render is v2. | Editability is the primary output requirement, above appearance. |
| D-4 | **Lives in `qbiz_assay`.** | `prioritize.py` in-package, core importing nothing Assay-specific. |

## 3. The constraint that governs the design

**Priority is derivable from facts. Effort is not.**

Impact is deterministic: `severity_weight × dimension_weight`, both registry values. Effort depends
on the client's team, tooling, and change process — nothing a collector observes.

Assay's credibility rests on one property (`findings.py`): *findings are deterministic facts; the
narrator explains but never alters them.* Effort estimates must therefore be **explicitly sourced**,
mirroring the existing `EvidenceType` pattern:

```python
class EstimateSource(str, Enum):
    DEFAULT    = "default"      # config's per-offering default — visible, tunable
    CONSULTANT = "consultant"   # a human typed it — highest trust
    ESTIMATED  = "estimated"    # an agent proposed it — unreviewed
    MEASURED   = "measured"     # RESERVED — see below, not implemented in v1
```

**`MEASURED` is reserved, not built. [E+C]** Both reviewers showed it has no data path: per-finding
counts live interpolated inside title f-strings (`dbt.py:147`) and in `CollectorResult.stats` under
ad-hoc per-collector keys with no link back to the finding. Building the join table would be
exactly what `config.py:9-11` calls a framework bug. Keep the enum member so stored matrices are
forward-compatible; do not implement it.

Challenger notes D-3 makes "internal-only" a *convention* while `[A4]` graduates read-only "from
principle to mechanism" — we'd be demanding of everyone else what we grant ourselves. Fair.
**Mitigation [C]:** the report renderer refuses to embed matrix output unless explicitly flagged.
Cheap, and it makes the constraint real.

## 4. Design

### 4.1 The unit: workstream **[C]**

A **workstream** is a coherent body of remediation work — by default one offering group, which is
already how the roadmap section organizes itself. A workstream carries its findings as evidence and
is the thing that gets an effort band.

```python
@dataclass(slots=True)
class Task:                        # a matrix row: one workstream, or a consultant-authored split
    id: str                        # offering id by default — stable by construction
    title: str
    impact: float                  # Σ impact_of(finding) over its findings
    effort: EffortBandId           # "S" | "M" | "L" | "XL"
    effort_source: EstimateSource
    priority: str = ""             # "P0".. — computed
    quadrant: str = ""             # computed
    findings: tuple[str, ...] = () # finding titles, as evidence
    depends_on: tuple[str, ...] = ()
    rationale: str = ""
    notes: str = ""                # consultant free text, never machine-written
```

Three v1 problems dissolve at this grain:

- **`Task.id` stability. [E+C]** Both reviewers flagged that `Finding` has no id, and that
  title-derived ids churn because dbt titles embed live counts *and* compute severity from
  thresholds (`dbt.py:146-147`) — so a re-run after the client fixes anything orphans the
  consultant's notes, which is v1 §10's self-declared worst outcome, caused by v1's own id scheme.
  At workstream grain **`id` is the offering id and is stable by construction.** No new field on
  `Finding`, no touching four collectors and their tests. **This alone is worth the regrain. [A]**
- **`overhead` vs `per_item` double-counting.** A workstream is estimated once. The distinction
  disappears; so does Challenger's finding that the quadrant plotted `per_item` while the roll-up
  added `overhead`, understating effort most in the quick-win quadrant.
- **Calibration has a real unit.** There will never be a calibration datum for "backfill 4
  descriptions"; there will be one for "dbt startup kit engagement." **[C]**

A consultant may split a workstream by hand into finer rows (authoring their own ids). That is the
editing affordance D-3 asks for, and it is where finer estimates belong — from a human, at a grain
they chose.

**Uncategorized CRITICALs get their own row. [C]** Findings with no offering do not fall to a
default effort. They collect into an **Immediate remediation** workstream whose effort renders
`n/a` — never a costed band. "Rotate this credential" is not a 3-to-5-day project and must never
print as one.

**INFO findings are excluded** from the matrix entirely. **[C]** They deduct zero and are often
"greenfield, you're fine" notes; costing them as P2 tasks is noise.

### 4.2 Priority axis — reuse the rubric

```python
def impact_of(finding: Finding, rubric: RubricConfig) -> float:
    return rubric.deduction_for(finding.severity) * rubric.weight_for(finding.dimension)
```

A workstream's impact is the sum over its findings. One authority, no second scale.

Note `weight: 0` is an explicitly supported override (`rubric.py:85-89`) and would zero a
CRITICAL's impact. **[C]** The severity floor (§4.3) is what saves that case — evidence the floor
is load-bearing, not decoration.

### 4.3 Quadrant and priority are **two different labels** **[C→A]**

v1 mapped quadrant→P-label directly, then added a critical floor as an exception — making "P0" mean
both *"cheap win"* and *"on fire."* Challenger correctly read that as the taxonomy being wrong
rather than needing an exception. The fix is to stop conflating them:

- **Quadrant** = *what kind of work this is.* Quick Win / Major Project / Fill-In / Thankless.
  Descriptive. This is the matrix.
- **Priority (P0–P3)** = *what to do first.* Ordering. This is the roadmap.

Priority is impact-banded with effort as the tiebreak inside a band, plus the floor:

1. `priority_floor: {critical: P0}` — any workstream containing a CRITICAL is P0.
2. Otherwise band by impact against config thresholds.
3. Within a band, order by `impact / effort_axis` descending.

Two labels, two meanings, no collision — and the "one document, two rankings" hazard §4.2 forbids
is gone, because the matrix and the roadmap now express different things rather than competing
orderings of the same thing.

**Quadrant thresholds are fixed config, not median splits. [E+C]** Median splitting is broken on a
5-value severity ladder — ties on the mode are the *normal* case, not an edge case, and v1's `n < 4`
guard named the wrong pathology. It is also wrong in principle: a consultant's 2×2 has its lines
drawn where they belong, not wherever the current sample's midpoint happens to fall. Fixed
thresholds are simpler, stable across re-runs, and tunable per engagement.

### 4.4 Effort config — Tier 0

```yaml
effort:
  bands:
    - { id: S,  label: Small,   days: [1, 2],   axis: 1.5 }
    - { id: M,  label: Medium,  days: [3, 5],   axis: 4 }
    - { id: L,  label: Large,   days: [6, 15],  axis: 10 }
    - { id: XL, label: Program, days: [16, 40], axis: 28 }
  defaults_by_offering:
    dbt_startup_kit:            L
    sensitivity_classification: L
    incident_agent:             M
    agent_harness:              M
    ai_advisory:                S
  thresholds: { impact_high: 50, effort_high: 6 }
  priority_bands: [ { min: 60, id: P0 }, { min: 30, id: P1 }, { min: 10, id: P2 }, { min: 0, id: P3 } ]
  priority_floor: { critical: P0 }
```

**This is not free. [E]** v1 claimed the existing `apply_overrides` absorbs it; that was
hand-waving. `config.py:196-258` is ~60 lines of bespoke per-section merge code with separate
hand-written blocks for each section — nothing generic. `effort:` costs a fifth merge block, new
dataclasses, a field on the frozen `AssessmentConfig`, and validators: **~120 lines plus ~120 test
lines, budgeted at zero in v1.**

`axis` is never rendered; the report prints label and day range.

### 4.5 Output — the primary v1 requirement (D-3)

The artifact the consultant edits **is** the artifact the renderer consumes.

- **Editable form: YAML**, one block per workstream. At workstream grain this is ~5–7 rows, not 13
  — a page a consultant can actually reason about.
- **`sync` is a merge, never an overwrite.** Preserves every `consultant` effort and every `notes`
  field, adds new workstreams, marks disappeared ones rather than deleting. Stable ids (§4.1) make
  this tractable; it remains the highest-risk code in the feature and gets tests as an explicit
  acceptance criterion.
- **No `ruamel.yaml`. [E]** v1's "comments preserved" would add a third dependency to a two-dep
  package. The `notes` field carries consultant prose instead; plain `yaml` is sufficient.
- **Rendered form: markdown** — quadrant table plus priority-ordered list with effort ranges.

### 4.6 CLI

```
qba assay prioritize init   <profile.yaml> --out workstreams.yaml
qba assay prioritize sync   <profile.yaml> workstreams.yaml     # merge, never clobber
qba assay prioritize render workstreams.yaml --out matrix.md
```

**[E]** `init` and `sync` each silently re-run the full assessment through `run_profile`. Accept an
existing assessment artifact as input instead, or state the re-run cost in the help text.

Under `qba assay` for v1 per D-1; the standalone phase promotes it to top-level `qba prioritize`
with an alias — a rename, not a redesign.

## 5. The agentic half

Modelled on the proven `Narrator` seam in `assessor.py` — Protocol plus deterministic fallback,
metered by the engine. Both reviewers endorsed this choice.

```python
class Estimator(Protocol):
    def estimate(self, tasks: list[Task], context: dict) -> EstimateResult: ...

class DefaultEstimator:      # zero-cost, zero-key: config defaults
```

Rules:

1. Runs under the harness at the same call-site pattern as narration in `engine.py`.
2. Declares a model-tier band via `harness/model_policy.py` — `Tier.MID` ceiling.
3. Everything it produces is tagged `ESTIMATED`.
4. **Never overwrites a `CONSULTANT` value.** Enforced in code.
5. Writes a **proposal** the consultant diffs and accepts — never a direct write. Acceptance flips
   `ESTIMATED → CONSULTANT` and lands in the audit trail.

**What the agent is actually better at.** Effort numbers are the weaker half. The stronger half is
**clustering findings into workstreams and identifying sequencing dependencies** — "you cannot
classify sensitivity before there is a catalog." At workstream grain this becomes the agent's
*primary* job rather than a side benefit: proposing how findings group and what blocks what. That
is judgment, not arithmetic, and it is the honest answer to "why an agent here at all."

**HITL is struck from v1. [E]** v1 claimed the accept gate was available now because `hitl.py`
ships. Verified: `hitl_checkpoint` and `ApprovalTransport.request_approval` are both `async`
(`hitl.py:55,90`) and Assay is synchronous end to end; no `ApprovalTransport` implementation exists
in-repo — the Slack side is an MCP tool, not a Python object satisfying the Protocol. **A-9 is
resolved: local CLI diff for v1.** Revisit when v2 goes client-facing.

## 6. The latent bug — ship it independently **[E+C]**

`report.py:113-116` ranks the roadmap by `-sum(deduction_for(severity))`, omitting dimension
weight, while `overall_score` (`rubric.py:76-90`) applies it. Real, and `profile.py`'s own docstring
example (`weight: 2.0`) triggers it.

Two corrections to how v1 described it, both from Engineer, both verified:

- It is **not** a "unification." There is no scorecard *ordering* to unify — rows render in
  registry order (`report.py:61`) — and `overall_score` is a weighted mean of scores, not a sum of
  weighted deductions, so it cannot consume `impact_of()`. It is a **3-line standalone change with
  two callers.**
- It is arguably a **design decision, not a bug**: offering groups span dimensions, so it is at
  least defensible to rank them unweighted. Flag it for David rather than silently "fixing" it.

Either way it is independent of the matrix. Ship it separately, now.

## 7. Sequencing

| Piece | Blocked by | When |
| --- | --- | --- |
| Roadmap ranking weight fix (§6) | nothing | **Now, standalone** |
| `effort:` config section + merge block + validators | nothing | Before Phase 3 |
| `prioritize.py`: `Task`, `EstimateSource`, `impact_of`, workstream grouping | above | same |
| `qba assay prioritize init / sync / render` | above | same |
| `Estimator` Protocol + `DefaultEstimator` | nothing | same |
| LLM estimator + dependency clustering | `[D3]` provider (soft — fallback ships without it) | Phase 3 |
| Client-facing polished render | D-3 v2 | Phase 4 |
| Standalone task lists + Jira (`mcp_jira` exists) | second adapter | Phase 4 |
| HITL accept gate | needs sync transport or async Assay | v2, not before |
| Effort calibration from closed engagements | RAG precedent corpus | Phase 5 |

**Size. [E]** Engineer costed v1 as written at 1400–1800 lines including tests — 2–3× what a
"before Phase 3" slot implies — and the cut version at ~600–700. The workstream regrain is smaller
than either: no id machinery on `Finding`, no median math, ~6 rows instead of 13. **Estimate
~500–700 lines including tests**, of which ~240 is the config plumbing in §4.4.

## 8. Open decisions

- **[A8] Effort default calibration.** Shipped defaults are guesses — `[A3]`'s problem one axis
  over. Do not quote a workstream total externally until closed.
- **[A9] ~~Accept-gate placement~~ — RESOLVED.** Local CLI diff for v1; HITL is not wired (§5).
- **[A10] Sync-merge conflict policy.** When a re-run's computed impact contradicts a stored
  `consultant` effort, keep the consultant value silently, keep and flag, or prompt? Leaning: keep
  and flag in the render.
- **[A11] Roadmap ranking weight (§6)** — genuine design question, not just a fix: should
  offering-group ranking apply dimension weight, given groups span dimensions? Needs David's call.
- **[A12] Workstream splitting.** Should `render` warn when a single workstream carries more than
  N findings, prompting the consultant to split it? Cheap, and it counteracts the grain being too
  coarse for a large estate.

## 9. Risks

| Risk | Severity | Mitigation |
| --- | --- | --- |
| `sync` destroys consultant-typed work | **High** | Stable ids (§4.1) + merge tests as acceptance criterion |
| Model output launders into facts | High | `EstimateSource` + review gate + `ESTIMATED` never auto-accepted |
| Effort axis is a lookup on our own price list | High → **mitigated** | Workstream grain; uncategorized criticals never costed |
| Effort defaults uncalibrated | Medium | [A8] |
| Workstream grain too coarse for a large estate | Medium | Consultant splitting + [A12] warning |
| Totals read as a quote | Medium (deferred by D-3) | Renderer flag makes internal-only a mechanism, not a promise |
| Scope creep past `[A4]` read-only | None | Prioritizing recommends; it does not fix |

## 10. Reviewer proposals I did not adopt

Recorded so they are not silently lost.

- **Replace the matrix with an offering-grained phase plan (Challenger, primary alternative).**
  Partially adopted — I took the grain, not the replacement. The matrix is what was asked for and
  what consultants use; the objection was about the *unit*, and regraining answers it.
- **Impact × Confidence instead of Impact × Effort (Challenger).** Genuinely interesting and nearly
  free — `EvidenceType` already carries confidence, and Challenger's point that *"every competitor
  claims an effort column, none can show provenance"* is a real differentiator. **Not v1** (it isn't
  what was asked for), but it is the strongest v2 candidate on the list and it composes with the
  matrix rather than replacing it — a third column, or a shading on the existing plot.
- **Cut quadrants entirely, ship a ranked list (Engineer).** Rejected — the 2D shape is the
  deliverable and the reason consultants use this instrument. Engineer's underlying objection was
  that the *math* was broken, which fixed thresholds at workstream grain resolves.
