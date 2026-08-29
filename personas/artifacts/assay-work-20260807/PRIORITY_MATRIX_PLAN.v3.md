# Assay — Recommendations Prioritization

*Draft plan **v3**, 2026-08-07. Author: Architect. **Scratch — not the real plan.** Intended to fold
into `assay/ASSAY_PLAN.md` after David's review.*

*Lineage: v1 → Engineer + Challenger review (`REVIEW_engineer.md`, `REVIEW_challenger.md`) → v2 →
prior-art slide from a previous engagement (Urgent × Strategic, P0–P3 contour bands) → v3. Earlier
drafts preserved alongside.*

*Provenance markers: **[E]** Engineer, **[C]** Challenger, **[PA]** prior-art slide, **[A]**
Architect ruling.*

> **Renamed from "Priority × Effort Matrix."** Impact×Effort is now one configuration of this
> feature, not the feature. See §0.

---

## 0. What changed from v2, and why

v2 hardcoded `impact` and `effort` as *the* two axes. A prior-engagement slide surfaced afterward
shows QBiz ranking recommendations to P0–P3 on **Urgent × Strategic**, with no effort axis at all
and curved contour bands rather than a 2×2.

That is not a different feature. It is the same instrument with different axes — and v2's
hardcoding was a direct violation of Assay's own core design rule, stated at `config.py:9-11`:
*if adding a domain requires editing core files, that is a framework bug.* v2 committed exactly
that bug, in a plan for that codebase. **[A]**

**The fix: axes are a registry.** Ship both axis sets, let a profile define more. Confirmed with
David that axis choice is a consultant call dependent on the client and the engagement's remit —
so neither can be the hardcoded one.

Three further corrections the prior art forces:

- **Contour bands replace quadrants, and the severity floor mostly disappears. [PA]** Those curved
  isolines let an item extreme on *one* axis reach P0 without scoring high on both. v2 needed a
  bolted-on `priority_floor: {critical: P0}` to get that behaviour, and Challenger read the floor as
  proof the taxonomy was broken. It wasn't — the *boundary shape* was. A straight-line 2×2 cannot
  express "urgent enough on its own"; a contour can, natively.
- **Grain is coupled to axis choice, which v2 concealed. [A]** v2's regrain to workstreams was
  forced almost entirely by effort needing scope data that `Finding` doesn't carry. Urgent,
  Strategic, and Confidence need no scope data — so under those axes, finding grain is viable
  again. Grain must therefore be *derived* from the axis set, not fixed.
- **This is a workshop instrument, not a scoring engine. [PA]** The slide says "flexibility to work
  with client based on their feedback." The axes get renegotiated live, in the room. That is a
  stronger requirement than D-3's editability: re-banding must be fast and CLI-overridable, not
  only reachable by editing YAML between runs.

**What survives from v2 unchanged:** the provenance-typing constraint (§3), `MEASURED` reserved,
HITL struck, no `ruamel`, sync-is-a-merge, uncategorized CRITICALs never costed, and the
independent `report.py` ranking fix (§7).

## 1. Why

Consultants rank engagement recommendations to P0–P3. Assay does half of it: `report.py` groups
findings by offering and ranks groups by summed severity deduction — one axis, no second dimension,
no bands. `ASSAY_PLAN.md` calls that section "a proposal skeleton"; a skeleton with one axis cannot
be scoped or sequenced.

## 2. Settled decisions

| # | Decision | Source |
| --- | --- | --- |
| D-1 | **Both use cases, phased.** Assay findings in v1; standalone task lists and Jira later. | David |
| D-2 | **Bands**, not raw engineer-days, wherever an effort-like axis is used. | David |
| D-3 | **Internal-only for v1.** Polished client-facing render is v2. | David |
| D-4 | **Lives in `qbiz_assay`.** Core imports nothing Assay-specific. | David |
| D-5 | **Both axis sets ship as selectable.** Which one to use is a consultant call, dependent on the client and what we were engaged to evaluate. | David, 2026-08-07 |

## 3. The constraint that governs the design

v2 framed this as "priority is derivable, effort is not." The prior art shows the real shape is
more general:

> **Every viable axis pair has one axis derived from the scan and one supplied by a human.**

| Axis set | Derived axis | Human axis |
| --- | --- | --- |
| `impact_effort` | Impact — `severity_weight × dimension_weight` | Effort — depends on the client's team and tooling |
| `urgent_strategic` **[PA]** | Urgent — severity is a direct proxy | Strategic — depends on the client's business goals |
| `impact_confidence` **[C]** | Both — `EvidenceType` already carries confidence | *(none — see §9)* |

This is structural, not a flaw to design away. Assay's credibility rests on one property
(`findings.py`): *findings are deterministic facts; the narrator explains but never alters them.*
So the human-supplied axis must be **explicitly sourced** — the same trick `EvidenceType` plays for
findings, generalized:

```python
class AxisSource(str, Enum):        # renamed from v2's EstimateSource — it tags any human axis
    DERIVED    = "derived"          # computed from findings — deterministic
    DEFAULT    = "default"          # config's per-offering default — visible, tunable
    CONSULTANT = "consultant"       # a human typed it — highest trust
    PROPOSED   = "proposed"         # an agent suggested it — unreviewed
    MEASURED   = "measured"         # RESERVED — not implemented, see below
```

**`MEASURED` stays reserved. [E+C]** Both reviewers showed it has no data path: per-finding counts
live interpolated inside title f-strings (`dbt.py:147`) and in `CollectorResult.stats` under ad-hoc
per-collector keys with no link back to the finding. Building the join would be the framework bug
`config.py:9-11` names. Keep the member for forward compatibility; do not implement it.

**Internal-only becomes a mechanism, not a promise. [C]** Challenger noted D-3 leaves this a
convention while `[A4]` graduates read-only "from principle to mechanism" — demanding of others what
we grant ourselves. The report renderer refuses to embed prioritization output unless explicitly
flagged.

## 4. Design

### 4.1 Axes as a registry — the core of v3

```yaml
prioritization:
  axis_sets:

    urgent_strategic:                       # [PA] — prior-art default
      label: "Urgency × Strategic value"
      axes:
        urgent:    { source: derived, from: severity, weight: 1.0 }
        strategic: { source: human,   scale: bands,   weight: 1.0, bands: [low, medium, high] }
      combine: { fn: power_mean, shape: 2.5 }
      grain: finding                        # neither axis needs scope data

    impact_effort:
      label: "Impact × Effort"
      axes:
        impact: { source: derived, from: impact_of, weight: 1.0 }
        effort: { source: human,   scale: bands, weight: 1.0, invert: true, requires_scope: true }
      combine: { fn: power_mean, shape: 2.5 }
      quadrants: [quick_win, major, fill_in, thankless]   # only meaningful for this set
      # grain omitted — derived as `workstream`, because effort requires_scope

  bands: [ {min: 0.75, id: P0}, {min: 0.50, id: P1}, {min: 0.25, id: P2}, {min: 0.0, id: P3} ]
  priority_floor: { critical: P0 }          # conditional — see §4.3
  default_axis_set: urgent_strategic
```

The engine iterates this registry. Adding Challenger's `impact_confidence` — or a client's own house
axes — is a config block, no code. That is the same "genericize before deepening" trade
`ASSAY_PLAN.md` Phase 2 already made deliberately, applied one level down.

### 4.2 Grain is derived, not configured **[A]**

An axis declares `requires_scope: true` when its value depends on how much work an item represents.
Then:

- **Any axis requires scope → grain is `workstream`** (one offering group by default, `id` = the
  offering id, stable across re-runs by construction).
- **No axis requires scope → grain defaults to `finding`**; a consultant may coarsen by hand.

This derivation is what makes v2's regrain conditional rather than universal, and it resolves the
`Task.id` stability problem both reviewers raised **[E+C]** without touching `Finding`: at workstream
grain the id is the offering id; at finding grain, ids only need to be stable *within* an axis set
that never re-groups, and the consultant authors ids for any hand-split row.

```python
@dataclass(slots=True)
class Item:                            # one row: a finding, or a workstream, per derived grain
    id: str
    title: str
    axis_values: dict[str, float]      # keyed by axis id — no hardcoded impact/effort
    axis_sources: dict[str, AxisSource]
    priority: str = ""                 # computed
    quadrant: str = ""                 # computed, only when the axis set defines quadrants
    findings: tuple[str, ...] = ()     # evidence
    depends_on: tuple[str, ...] = ()
    rationale: str = ""
    notes: str = ""                    # consultant free text, never machine-written
```

`axis_values` as a dict, not named fields, is the whole point — core code never names an axis.

### 4.3 Bands from contours **[PA]**

Normalize each axis to 0–1, then combine:

```
score = ( Σ wᵢ · xᵢ^p )^(1/p)  ·  (1 / Σ wᵢ)^(1/p)      # power mean, shape parameter p
```

- `p = 1` → weighted sum → **straight diagonal** boundaries (a conventional 2×2 feel).
- `p → ∞` → `max(x)` → **right-angle** contours; extreme on one axis alone is sufficient.
- `p ≈ 2.5` → the **rounded corner** the prior-art slide draws.

Band by thresholds on `score`. This is one small function, config-parameterized, and it subsumes
v2's quadrant test entirely.

**The severity floor becomes conditional. [PA→A]** Under `power_mean` with `shape ≥ 2`, a CRITICAL
(urgent = 1.0) clears the P0 threshold on its own — the floor is redundant, which is precisely the
prior art's advantage over v2's exception-patch. But a consultant who selects `fn: weighted_sum`
reintroduces the gap. Keep `priority_floor` in config, document that it is unnecessary under the
default shape and load-bearing under `weighted_sum`. It also still guards the `weight: 0` case
Challenger found (`rubric.py:85-89`), where an override can zero a CRITICAL's derived impact.

**Quadrants survive only where they mean something. [A]** "Quick Win / Major Project" is a statement
about effort; it is meaningless on Urgent × Strategic. So `quadrants:` is an optional per-axis-set
decoration, rendered when defined and absent otherwise. Priority (P0–P3) is the universal output;
quadrant is the Impact×Effort flavour text. This also resolves v2's "P0 means two things" problem
without needing v2's two-label workaround — the contour *is* the priority, and it has one meaning.

### 4.4 Derived axis values

```python
def impact_of(finding: Finding, rubric: RubricConfig) -> float:
    return rubric.deduction_for(finding.severity) * rubric.weight_for(finding.dimension)
```

`urgent` uses severity directly; `impact` uses the product above. One authority — the rubric — for
every derived axis, so no second scale can drift from the scorecard.

### 4.5 The human axis — defaults and capture

For `effort`, per-offering band defaults (v2's table, unchanged), with **uncategorized CRITICALs
never costed [C]**: findings with no `offering` collect into an **Immediate remediation** row whose
effort renders `n/a`. Verified — both CRITICALs in the shipped demo have no offering
(`ai_usage.py:133-142`), so v2's fallback would have printed *"rotate the credential now — Medium,
3–5 days."*

For `strategic`, there is no defensible default — business goals aren't in the artifacts. Ship it
**unset**, rendering as `—`, and let the consultant fill it in. An unset human axis degrades the
score to the derived axis alone rather than guessing, and the render says how many rows are unset.

**INFO findings are excluded** from prioritization entirely. **[C]**

### 4.6 Output and workshop mode **[PA]**

The artifact the consultant edits **is** the artifact the renderer consumes.

- **Editable form: YAML**, one block per item. **No `ruamel.yaml` [E]** — v2's "preserve comments"
  would add a third dependency to a two-dep package; the `notes` field carries consultant prose.
- **`sync` is a merge, never an overwrite.** Preserves every `consultant` value and every `notes`
  field, adds new items, marks disappeared ones rather than deleting. Highest-risk code in the
  feature; merge tests are an explicit acceptance criterion.
- **Workshop re-banding.** `render` accepts axis-set selection, weight, and shape overrides on the
  command line so the banding can be redrawn live in front of a client without editing files:

```
qba assay prioritize init   <profile.yaml> --axes urgent_strategic --out items.yaml
qba assay prioritize sync   <profile.yaml> items.yaml
qba assay prioritize render items.yaml --weight strategic=1.5 --shape 3 --out matrix.md
```

**[E]** `init` and `sync` each silently re-run the full assessment via `run_profile`. Accept a
persisted assessment as input, or state the re-run cost in the help text.

Under `qba assay` for v1 per D-1; the standalone phase promotes it to top-level `qba prioritize`
with an alias.

### 4.7 A Tier-0 win from the slide **[PA]**

The slide's left column lists Data Management categories — Architecture & Design, Risk & Compliance,
Policy & Process, Cost Optimization, Infrastructure & Tooling — which is close to an alternative
*dimension set*. Shipping it as a rubric override (`config/qbiz_engagement_categories.yaml`) is
Tier-0 config, no code, and it makes Assay's output land in vocabulary the client deck already uses.
Cheap; do it alongside.

## 5. The agentic half

Modelled on the proven `Narrator` seam in `assessor.py` — Protocol plus deterministic fallback,
metered by the engine. Both reviewers endorsed the choice.

```python
class AxisEstimator(Protocol):
    def propose(self, items: list[Item], axis: str, context: dict) -> ProposalResult: ...

class DefaultEstimator:      # zero-cost, zero-key: config defaults; leaves `strategic` unset
```

Rules: runs under the harness at narration's call-site pattern; declares a `Tier.MID` ceiling via
`harness/model_policy.py`; everything it emits is tagged `PROPOSED`; **never overwrites a
`CONSULTANT` value**, enforced in code; writes a *proposal* the consultant diffs and accepts, never
a direct write — acceptance flips `PROPOSED → CONSULTANT` and lands in the audit trail.

**The axis change makes the agent more useful, not less. [A]** Effort is a poor LLM task — it
depends on team facts the model cannot see. **Strategic value is a genuinely good one**: client
goals are usually *written down*, in the very policy docs, strategy decks, and runbooks that
`ASSAY_PLAN.md`'s Phase 4 RAG-backed document-evidence collector already plans to ingest. An agent
proposing "this is high strategic value because your own Q3 charter names it" is grounded,
citable, and exactly the evidence-quality upgrade that collector exists to deliver. That is a real
synergy between this feature and a already-planned one, and it argues for sequencing the LLM
estimator *after* the document-evidence collector rather than beside the narrator.

The agent's other job stands: **clustering findings into workstreams and identifying sequencing
dependencies** — judgment, not arithmetic.

**HITL struck from v1. [E]** Verified: `hitl_checkpoint` and `ApprovalTransport.request_approval`
are both `async` (`hitl.py:55,90`); Assay is synchronous end to end, and no `ApprovalTransport`
implementation exists in-repo — the Slack side is an MCP tool, not a Python object satisfying the
Protocol. **[A9] resolved: local CLI diff for v1.**

## 6. Corrections to the record

Verified in code, changing earlier assumptions: `harness/hitl.py` and `harness/model_policy.py` are
built and shipped (but see the async mismatch above); `mcp/mcp_jira/` exists, so D-1's Jira
expansion is a thin caller of an existing MCP server per the repo reuse rule, not new integration
build.

## 7. The latent bug — ship it independently **[E+C]**

`report.py:113-116` ranks the roadmap by `-sum(deduction_for(severity))`, omitting dimension weight,
while `overall_score` (`rubric.py:76-90`) applies it. Real, and `profile.py`'s own docstring example
(`weight: 2.0`) triggers it.

Two corrections from Engineer, both verified: it is **not** a "unification" — rows render in
registry order (`report.py:61`) so there is no scorecard *ordering* to unify, and `overall_score` is
a weighted mean of scores rather than a sum of weighted deductions, so it cannot consume
`impact_of()`. It is a **3-line standalone change with two callers**. And it is arguably a **design
decision, not a bug**: offering groups span dimensions, so ranking them unweighted is defensible.

Independent of this feature. Ship separately, now, pending **[A11]**.

## 8. Sequencing

| Piece | Blocked by | When |
| --- | --- | --- |
| Roadmap ranking weight fix (§7) | [A11] | **Now, standalone** |
| `prioritization:` config section + merge block + validators | nothing | Before Phase 3 |
| `prioritize.py`: `Item`, `AxisSource`, axis registry, `power_mean`, banding | above | same |
| Both shipped axis sets + derived-grain rule | above | same |
| `qba assay prioritize init / sync / render` + workshop overrides | above | same |
| `AxisEstimator` Protocol + `DefaultEstimator` | nothing | same |
| Engagement-categories rubric override (§4.7) | nothing | same — Tier 0, no code |
| LLM estimator for `strategic` | `[D3]` provider; **better after** Phase 4 doc-evidence collector | Phase 4 |
| Dependency clustering | `[D3]` (soft) | Phase 3–4 |
| Client-facing polished render | D-3 v2 | Phase 4 |
| Standalone task lists + Jira | second adapter | Phase 4 |
| HITL accept gate | needs a sync transport or an async Assay | v2, not before |
| Axis calibration from closed engagements | RAG precedent corpus | Phase 5 |

**Size, honestly. [E]** Engineer costed v1-as-written at 1400–1800 lines including tests and a cut
version at ~600–700. v3 is **larger than v2's ~500–700 — call it ~800–1000** — because the axis
registry is real indirection. That is a deliberate trade, and the same one `ASSAY_PLAN.md` Phase 2
made on purpose ("genericize before deepening... *before* any new collector was written, so every
later collector lands on the plugin API instead of deepening the hardcoding"). Two axis sets exist
*today*; hardcoding one and retrofitting the other later costs more than building the registry now.
If that trade is wrong here, the cut is: ship `urgent_strategic` only, keep the registry shape,
skip the second axis set and the quadrant decoration (~600).

## 9. Open decisions

- **[A8] Axis calibration.** Effort defaults and band thresholds are guesses — `[A3]`'s problem one
  axis over. Do not quote externally until closed.
- **[A9] ~~Accept-gate placement~~ — RESOLVED.** Local CLI diff for v1.
- **[A10] Sync-merge conflict policy.** When a re-run's derived axis contradicts a stored
  `consultant` value, keep silently / keep and flag / prompt? Leaning: keep and flag in the render.
- **[A11] Roadmap ranking weight (§7).** Genuine design question: should offering-group ranking
  apply dimension weight, given groups span dimensions? Needs David's call.
- **[A12] Workstream splitting warning** when one workstream carries more than N findings.
- **[A13] Prior-art provenance. [A]** The Urgent × Strategic slide shows the methodology was
  *presented*. It does not establish that it was used, that it worked, or that it is the house
  standard — and "built for X does not mean used for X." Ask whoever ran that engagement before
  treating it as the default. **This gates `default_axis_set`, nothing else.**
- **[A14] Is `impact_confidence` worth shipping as a third set? [C]** It is nearly free —
  `EvidenceType` already carries confidence, and it needs *no* human axis at all, making it the only
  fully-derivable set. Challenger's argument that *"every competitor claims an effort column, none
  can show provenance"* is a real differentiator. Not v1; strongest v2 candidate.

## 10. Risks

| Risk | Severity | Mitigation |
| --- | --- | --- |
| `sync` destroys consultant-typed work | **High** | Derived-grain stable ids (§4.2) + merge tests as acceptance criterion |
| Model output launders into facts | High | `AxisSource` + `PROPOSED` never auto-accepted + renderer flag |
| A human axis ships unset and reads as "low" | **High** *(new in v3)* | `strategic` renders `—`, never `0`; score degrades to the derived axis; render reports unset count |
| Axis registry is over-built for two axis sets | Medium | Phase-2 precedent; §8 names the cut if the trade is wrong |
| Axis defaults uncalibrated | Medium | [A8] |
| Grain too coarse for a large estate | Medium | Consultant splitting + [A12] |
| Totals read as a quote | Medium (deferred by D-3) | Renderer flag makes internal-only a mechanism |
| Scope creep past `[A4]` read-only | None | Prioritizing recommends; it does not fix |

## 11. Reviewer and prior-art proposals not adopted

- **Replace the matrix with an offering-grained phase plan (Challenger).** Partially adopted — took
  the grain insight, made it conditional on axis choice (§4.2) rather than universal.
- **Cut quadrants entirely (Engineer).** Adopted in substance: contour bands replace the quadrant
  *math*; quadrant survives only as optional flavour text on Impact×Effort (§4.3).
- **`impact_confidence` as the axis pair (Challenger).** Deferred to [A14], not rejected — it is now
  cheap to add precisely because §4.1 made axes a registry.
