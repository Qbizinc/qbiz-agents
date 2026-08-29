# Assay — Priority × Effort Matrix

*Draft plan v1, 2026-08-07. Author: Architect. **Scratch — not the real plan.** Intended to fold
into `assay/ASSAY_PLAN.md` after review. Status: awaiting Engineer and Challenger review.*

---

## 1. Why

Consultants have historically ranked engagement tasks on a Priority-vs-Effort matrix (P0/P1/P2).
Assay already does half of this and only half: [`report.py`](../../../assay/src/qbiz_assay/report.py)
groups findings by offering and ranks the groups by summed severity deduction. That is
risk-ordering on a single axis. **There is no effort axis anywhere in `qbiz_assay` today.**

The roadmap section is described in `ASSAY_PLAN.md` as "a proposal skeleton." A proposal skeleton
with no effort dimension cannot be scoped. Adding the second axis upgrades the section that is
already the commercial payload of the deliverable.

## 2. Settled decisions (David, 2026-08-07)

| # | Decision | Consequence for this plan |
| --- | --- | --- |
| D-1 | **Both use cases, phased.** Assay findings are the primary and only v1 target. Standalone consultant task lists — and agent-created Jira tickets — are a *future* enhancement. | The `Task` model must not be `Finding`-shaped, so the standalone path is a later addition rather than a rewrite. But v1 ships only the assay-derived path. |
| D-2 | **Effort in bands**, not raw engineer-days. | T-shirt bands with a day *range* shown; numeric midpoints exist for axis math only and are never printed. |
| D-3 | **Internal-only artifact for now.** A consultant may choose to show it to a client, cleaning it up first. A polished client-facing render is v2. | Output must be **easy for a consultant to edit** — that is the primary output requirement, above looking good. No "indicative, not a quote" boilerplate needed in v1, because v1 never auto-renders into the client report. |
| D-4 | **Lives in `qbiz_assay`.** Not a new shared package. | `prioritize.py` inside the package, with a core that imports nothing Assay-specific, so promotion later is a file move. |

## 3. The constraint that governs the design

**Priority is derivable from facts. Effort is not.**

Impact already exists deterministically: `severity_weight × dimension_weight`, both registry
values from `config/qbiz_baseline.yaml`. Effort depends on the client's team, tooling, and change
process — nothing any collector observes.

Assay's credibility rests on one property, stated in `findings.py`: *findings are deterministic
facts; the narrator explains them but can never alter them.* If an agent assigns effort and that
silently becomes a **P0** label, model output has been laundered into the facts column and the
property is broken. This is the default outcome unless designed against.

**Mitigation — reuse the `EvidenceType` pattern.** `EvidenceType` tags how a *finding* knows what
it claims and the report renders the distinction. Do the same for effort:

```python
class EstimateSource(str, Enum):
    MEASURED   = "measured"     # arithmetic over a countable fact (4 untested models × rate)
    DEFAULT    = "default"      # the config's per-offering default — visible and tunable
    CONSULTANT = "consultant"   # a human typed it — highest trust
    ESTIMATED  = "estimated"    # an agent proposed it — unreviewed
```

D-3 lowers the stakes here (nothing reaches a client unreviewed in v1) but does **not** remove
them: the moment v2 renders client-facing, the provenance field must already be in the data or
every stored matrix from v1 is untyped and unusable. Add it now; it is nearly free now and
expensive to retrofit.

## 4. Design

### 4.1 `prioritize.py` — the core

```python
@dataclass(slots=True)
class Task:
    id: str
    title: str
    impact: float                    # rubric-derived, or supplied on the same ladder
    effort: EffortBandId             # "S" | "M" | "L" | "XL", ids from config
    effort_source: EstimateSource
    priority: str = ""               # "P0".. — computed, not authored
    quadrant: str = ""               # computed
    offering: OfferingId | None = None
    dimension: DimensionId | None = None
    depends_on: tuple[str, ...] = ()
    rationale: str = ""
    notes: str = ""                  # consultant free text, never machine-written
```

`Finding → Task` is an **adapter function**, not inheritance or a subclass. Per D-1 this is what
lets the standalone path land later as a second adapter rather than a refactor. The core scoring
functions take `Task` and `RubricConfig` and nothing else.

### 4.2 Priority axis — reuse the rubric, do not invent a second scale

```python
def impact_of(finding: Finding, rubric: RubricConfig) -> float:
    return rubric.deduction_for(finding.severity) * rubric.weight_for(finding.dimension)
```

Non-negotiable: a second priority scale would put two disagreeing rankings in one document. The
rubric is already the ranking authority; the matrix consumes it.

### 4.3 Effort axis — config, Tier 0

```yaml
effort:
  bands:
    - { id: S,  label: Small,   days: [1, 2],   axis: 1.5 }
    - { id: M,  label: Medium,  days: [3, 5],   axis: 4 }
    - { id: L,  label: Large,   days: [6, 15],  axis: 10 }
    - { id: XL, label: Program, days: [16, 40], axis: 28 }
  defaults_by_offering:
    dbt_startup_kit:            { per_item: S, overhead: M }
    sensitivity_classification: { per_item: M, overhead: L }
    incident_agent:             { per_item: M, overhead: M }
    agent_harness:              { per_item: M, overhead: L }
    ai_advisory:                { per_item: S, overhead: S }
  fallback: { per_item: M, overhead: M }     # uncataloged offering / no offering
```

Parsed and merged by the existing `apply_overrides` machinery in `config.py`, so an engagement
profile retunes effort exactly the way it retunes weights. `axis` is the midpoint used for
quadrant math and is **never rendered**; the report prints the label and the day range.

**Overhead vs. per-item.** Findings mapping to one offering share setup cost — "backfill 4
descriptions" and "backfill 2 more" is one pass, not two. Naive summing overcounts every roadmap
total, and the roadmap total is the number a proposal would quote. v1 computes
`offering_total = overhead + Σ(per_item)`; the schema above permits it from day one.

### 4.4 Quadrant and P-label

The 2D shape *is* the deliverable — the matrix communicates what a ranked list cannot. So:

1. **Quadrant** is the primary output. Split on the median of each axis across the task set
   (not fixed thresholds — a set of uniformly-critical findings should still separate).
   `quick_win` (high impact, low effort) / `major` / `fill_in` / `thankless`.
2. **P-label** derives from quadrant via a config map:
   `{quick_win: P0, major: P1, fill_in: P2, thankless: P3}`.
3. **Within a band**, order by `impact / effort_axis` descending.
4. **Severity floor overrides everything**: `priority_floor: {critical: P0}`.

Rule 4 is not optional. `assessor.py` already prints *"Critical items are remediate-now: they are
exposures, not backlog."* A matrix filing a hardcoded credential under "Major Project — later"
would contradict the report's own executive summary two pages earlier.

Median splitting has a known degenerate case (n < 4, or all items in one band) — fall back to
fixed thresholds from config below a configurable minimum task count.

### 4.5 Output format — the primary v1 requirement (D-3)

The artifact a consultant edits **is** the artifact the renderer consumes. Round-tripping is the
whole feature; a one-way render is not useful.

- **Editable form: YAML.** One block per task, `id` stable across regeneration, comments
  preserved where possible. YAML over CSV because `depends_on` is a list and `notes` is prose —
  both are miserable in a spreadsheet cell. (CSV export is the natural companion for the D-1
  standalone phase, where a spreadsheet *is* the consultant's starting point.)
- **Regeneration is a merge, not an overwrite.** Re-running against an updated assessment must
  preserve every `consultant`-sourced effort and every `notes` field, add new findings, and mark
  disappeared ones rather than deleting them. **Destroying a consultant's typed work is the worst
  outcome this feature can produce** and it is the single most likely bug.
- **Rendered form: markdown** — a quadrant table plus a per-offering roll-up with effort totals.
  Same renderer Assay's roadmap section will call in v2.

### 4.6 CLI

```
qba assay prioritize init  <profile.yaml> --out tasks.yaml     # impact computed, effort defaulted
qba assay prioritize sync  <profile.yaml> tasks.yaml           # re-run, merge, never clobber
qba assay prioritize render tasks.yaml --out matrix.md
```

Under `qba assay` for v1, per D-1: the only v1 source is an assessment. The D-1 standalone phase
promotes this to a top-level `qba prioritize` group with `assay` as one input adapter among
several — a rename with an alias, not a redesign.

## 5. The agentic half

Modelled on the `Narrator` seam in `assessor.py` — Protocol + deterministic fallback, metered by
the engine. That pattern is proven in this codebase; re-use it rather than inventing a second
agent shape.

```python
class Estimator(Protocol):
    def estimate(self, tasks: list[Task], context: dict) -> EstimateResult: ...

class DefaultEstimator:      # zero-cost, zero-key: config defaults + measured counts
```

Rules the agentic path obeys:

1. **Runs under the harness** at the same call site pattern as narration in `engine.py` —
   `CostGovernor`, `LoopGuard`, `AuditLog`.
2. **Declares a model-tier band** via `harness/model_policy.py` (`Tier.MID` is the ceiling;
   estimation is judgment, not frontier reasoning). This module ships today.
3. Everything it produces is tagged `ESTIMATED`.
4. **It never overwrites a `CONSULTANT` value.** Enforced in code, not convention.
5. It writes a **proposal** the consultant diffs and accepts — never a direct write into
   `tasks.yaml`. Acceptance flips `ESTIMATED → CONSULTANT` and lands in the audit trail.

**What the agent is actually better at.** Effort numbers are the weaker half. The stronger half is
**clustering findings into coherent workstreams and identifying sequencing dependencies** — "you
cannot classify sensitivity before there is a catalog"; "test coverage work needs CI first." That
is judgment, not arithmetic, and it is the honest answer to "why an agent here at all." It
populates `depends_on`, which reorders the matrix, so it carries the same provenance and review
gate.

**Human accept gate.** `harness/hitl.py` (Component 8, `ApprovalTransport` protocol) exists today
and the Slack MCP implements the matching shape. The accept gate is therefore **not blocked on
Phase 5** as originally assumed — it is available now. Whether to wire it in v1 or leave
acceptance as a local CLI diff is an open item (see §8, A-9).

## 6. Corrections to the record

Three things verified in the code that change earlier assumptions:

- `harness/hitl.py` and `harness/model_policy.py` are **built and shipped**, not future work.
- `mcp/mcp_jira/` **exists**. The D-1 "agents create Jira tickets" expansion is a thin caller of
  an existing MCP server per the repo reuse rule — not new integration build.

## 7. Latent bug to fix as part of this work

`report.py` ranks the roadmap by `-sum(deduction_for(severity))` — **it does not apply dimension
weight**, while `overall_score` in `rubric.py` does. Invisible today because every baseline weight
is `1.0`. The moment a profile reweights dimensions — advertised in `ASSAY_PLAN.md` and
`USE_CASES.md` as *the* Tier-0 client-tuning move — the scorecard and the roadmap rank by
different arithmetic inside one document.

Fix: one `impact_of()` used by the scorecard ordering, the roadmap ordering, and the matrix.

## 8. Sequencing

| Piece | Blocked by | When |
| --- | --- | --- |
| `prioritize.py` core, `Task`, `EstimateSource`, effort config | nothing | **Before Phase 3** |
| `impact_of()` unification + roadmap ranking fix (§7) | nothing | same |
| `qba assay prioritize init / sync / render` | above | same |
| `Estimator` Protocol + `DefaultEstimator` | nothing | same |
| LLM estimator + dependency clustering | `[D3]` provider (soft — fallback ships without it) | Phase 3, alongside the LLM narrator |
| HITL accept gate via Slack MCP | nothing (hitl.py ships) | v1 or Phase 3 — see A-9 |
| Client-facing polished render | D-3 v2 | Phase 4 |
| Standalone task lists + Jira ticket creation (D-1) | `mcp_jira` exists; needs the second adapter | Phase 4 |
| **Calibrating effort defaults from actual closed engagements** | RAG precedent corpus | Phase 5 |

That last row matters: actual effort from completed engagements is the calibration substrate the
open `[A3]` needs, and it calibrates *both* axes rather than only scores.

## 9. New open decisions

- **[A8] Effort default calibration.** The shipped `defaults_by_offering` values are guesses, with
  exactly the `[A3]` problem one axis over. Do not quote a roadmap total externally until closed.
- **[A9] Accept-gate placement.** `hitl.py` is available now. Is agent-proposed effort
  consequential enough to warrant a Slack approval in v1, or is a local CLI diff sufficient given
  D-3 keeps everything internal? Leaning: local diff for v1, HITL when v2 goes client-facing.
- **[A10] Sync-merge conflict policy.** When a re-run's `measured` effort contradicts a stored
  `consultant` value, what happens? Options: keep consultant silently, keep consultant and flag,
  or prompt. Leaning: keep and flag in the render.

## 10. Risks

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Model output launders into facts | High | `EstimateSource` provenance + review gate |
| `sync` destroys consultant-typed work | **High** | Merge semantics + tests as an explicit acceptance criterion |
| Two disagreeing rankings in one report | Medium | Single `impact_of()` (§7) |
| Roadmap totals read as a quote | Medium (deferred by D-3) | Internal-only in v1; revisit before v2 |
| Effort defaults uncalibrated | Medium | [A8], same discipline as [A3] |
| Scope creep past `[A4]` read-only | None | Prioritizing is still recommending, not fixing |
