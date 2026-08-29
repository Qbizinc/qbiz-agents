# Assay — Recommendations Prioritization

*Draft plan **v4**, 2026-08-07. Author: Architect. **Scratch — not the real plan.***

*Lineage: v1 → Engineer + Challenger round 1 → v2 → prior-art slide → v3 → Engineer + Challenger
round 2 → v4. All drafts and both review rounds preserved alongside.*

*Provenance: **[E]** Engineer, **[C]** Challenger, **[PA]** prior-art slide, **[D]** David,
**[A]** Architect.*

---

## 0. What changed from v3, and why

Round 2 was largely correct and I verified every load-bearing claim myself before accepting it.

**The disqualifying finding. [C]** v3's *default* configuration — `urgent_strategic` with `strategic`
unset and "degrade to the derived axis" — makes `urgent` a normalized severity, which my own band
thresholds map back to P0/P1/P2/P3 as an exact bijection with `Severity`. Over the demo's 13
findings, v3 shipped roughly 900 lines to produce a severity sort. Confirmed by my own arithmetic.

**The math error. [E+C]** §4.3 claimed "shape ≥ 2 makes the severity floor redundant." The true
crossover is **p ≥ 2.409** (`2^(-1/p) ≥ 0.75`); at p = 2 a CRITICAL scores 0.707 → P1. Both
reviewers derived 2.409 independently, blind to each other. My own §4.6 example command
(`--weight strategic=1.5 --shape 3`) demoted CRITICALs to P1.

**The structural error. [C]** I imported the slide's contour shape without checking it against the
slide's axis *semantics*. "Extreme on one axis is sufficient" is correct for two **value** axes —
which is what the slide has — and wrong when one axis is a **cost**. Verified: with `invert: true`,
a zero-impact task priced S scores 0.717 (P1) while a HIGH priced XL scores 0.474 (P2). The slide
is the proof of the distinction, not a counterexample to it.

**Speculative generality. [E]** The axis registry doesn't generalize where the cost is: `from:
severity` / `from: impact_of` are dispatch keys into a code-side resolver, so every derived axis
needs code regardless — making v3's "a client's house axes are a config block, no code" untrue. And
the two shipped sets are not two instances: with every baseline weight at 1.0, `impact_of` *is*
`urgent`. They differ by a boolean and two strings. My Phase-2 precedent doesn't transfer — Phase 2
genericized ahead of an *external* population; here the population is two, both ours, both closed
by D-5.

**Two things I dropped and am now taking. [E]** The `Finding.key` prerequisite (raised round 1,
dropped twice without counter-argument) and the sync-merge mechanisms I hollowed out to a headline.
D-6's override path makes per-row human data real, so both are genuinely required — see §4.2, §4.6.

**Sizing.** I lowballed twice. v3 claimed ~800–1000; Engineer costs it at ~1600–2100. §8 carries an
honest number this time.

## 1. Settled decisions

| # | Decision | Source |
| --- | --- | --- |
| D-1 | Assay findings in v1; standalone task lists and Jira later. | David |
| D-2 | Effort in bands, not engineer-days. | David |
| D-3 | Internal-only for v1; polished client-facing render is v2. | David |
| D-4 | Lives in `qbiz_assay`. | David |
| D-5 | Both axis sets ship as selectable; which to use is a consultant call. | David |
| D-6 | **Strategic value is hybrid: derived from dimension weights, consultant-overridable per item, provenance-tagged.** | David, 2026-08-07 |
| D-7 | **Contour curvature is a finite shape parameter (p ≈ 3–5), not `max()`.** Confirmed against the original slide: mostly-but-not-entirely flat, then plunging. | David, 2026-08-07 |

## 2. The design in one paragraph

Every recommendation gets two coordinates. **Urgency** is derived from severity. **Strategic value**
is derived from the client-set weight of the dimension it belongs to — captured once, in a scoping
conversation, using `rubric.dimensions[].weight`, which ships today — and may be overridden on an
individual row in a workshop, with the override tagged `CONSULTANT`. Both coordinates are therefore
always present; nothing is ever blank. The two are combined by a power mean whose shape parameter
reproduces the prior-art contour, and banded to P0–P3. Effort is an *alternative* second axis for
engagements that want Impact × Effort, at workstream grain, with different combination rules
because it is a cost rather than a value.

## 3. Why the human input goes at dimension grain **[C]**

Challenger's proposal, adopted as the core: **strategic value is a property of a business theme, not
of a task.** Asking a consultant to type a strategic value on each of thirteen findings invents
thirteen opinions where the client has one; asking the client to rank six dimensions once produces a
real answer at a grain that is stable across re-runs and comparable across engagements.

It also uses machinery that already exists: `rubric.dimensions[].weight` is parsed
(`config.py:104-112`), merged (`config.py:220-236`), and already advertised in `ASSAY_PLAN.md` and
`USE_CASES.md` as *the* Tier-0 client-tuning move. The strategic axis is a re-read of a field the
framework already collects for scoring.

**The slide's unread list. [C→PA]** v3 mined "Data Management categories" and ignored "Most
significant challenges" — Data Confidence, Development Velocity, Cost Efficiency, Security Risk.
Those four are *exactly* the business themes a client would rank. Ship a challenge→dimension map as
Tier-0 config so the client ranks four themes in their own vocabulary and it propagates to the six
dimension weights:

```yaml
challenges:                      # client-facing vocabulary; maps onto the rubric
  data_confidence:      { dimensions: [data_quality, documentation] }
  development_velocity: { dimensions: [operations] }
  cost_efficiency:      { dimensions: [cost] }
  security_risk:        { dimensions: [governance, ai_governance] }
```

## 4. Design

### 4.1 Axis sets are two constants, not a registry **[E]**

```python
URGENT_STRATEGIC = AxisSet(          # default
    id="urgent_strategic",
    x=Axis("strategic", derive=strategic_of, max=STRATEGIC_MAX, overridable=True),
    y=Axis("urgent",    derive=urgent_of,    max=URGENT_MAX),
    combine=PowerMean(shape=3.0),    # [D7]
    grain=Grain.RECOMMENDATION,
)

IMPACT_EFFORT = AxisSet(
    id="impact_effort",
    x=Axis("effort", source=HUMAN, scale=EFFORT_BANDS, is_cost=True),
    y=Axis("impact", derive=impact_of, max=IMPACT_MAX),
    combine=Quadrant(thresholds=...),          # NOT a contour — see §4.3
    quadrants=["quick_win", "major", "fill_in", "thankless"],
    grain=Grain.WORKSTREAM,                    # effort needs scope
)
```

Flat config exposes only what a profile actually retunes — `shape`, weights, band thresholds,
effort defaults, the default axis set. One merge block, not a two-level nested merge. Saves the
~250–400 lines Engineer identified, and loses nothing real: derived axes need code either way, so
"add your own axis set" was never a config-only move.

### 4.2 Grain and stable ids — taking the prerequisite I dropped **[E]**

D-6's override path means individual rows carry hand-typed data that `sync` must never destroy. That
requires stable ids, and v3's claim that derived grain dissolved the problem was **false at finding
grain**: verified, `dbt.py:143` and `dbt.py:195` both emit `data_quality` / `dbt_startup_kit` /
`subject=None`, so the natural composite key *collides*; titles embed live counts (`dbt.py:147`),
severities are computed from thresholds (`dbt.py:146`), and the collector name is discarded at
`engine.py:204`.

**Adopt `Finding.key`** — an explicit, collector-authored stable identifier:

```python
@dataclass(slots=True)
class Finding:
    key: str                 # NEW — e.g. "dbt.test_coverage"; stable across runs, unique per collector
    ...
```

Cost: one field, four collectors, their tests. Engineer named this in round 1; I dropped it twice
without argument. It is the honest fix and there isn't a cheaper one that survives a re-run.

**Grain is `recommendation`** by default — a finding plus its remediation, which is what the prior
art plots **[C]**, and what `id = f"{collector}.{finding.key}"` identifies stably. `workstream` grain
(id = offering id) is used whenever an axis `is_cost`, because effort needs scope.

### 4.3 Combination — contours for value×value, quadrants for value×cost **[C+PA]**

Normalize each axis to 0–1 against a **declared absolute maximum**, never against the observed set.
**[E]** Set-relative normalization reintroduces exactly the degeneracy that killed v1's median split,
and — worse — *promotes* the next-worst item to P0 as soon as a client fixes something. Absolute
maxima also make scores comparable across engagements, which is what `[A8]` calibration needs.

**Two value axes → power-mean contour:**

```
score = ( Σ wᵢ·xᵢ^p / Σ wᵢ )^(1/p)
```

- `p = 1` → weighted sum → straight diagonals.
- `p = 2.409` → **exact crossover**: a lone maximum on one axis reaches the 0.75 P0 threshold.
- `p = 3.0` → shipped default. Mostly-flat-then-plunging, matching the prior art **[D7]**, and
  comfortably above the crossover.
- `p → ∞` → `max()` → square corner. Explicitly *not* what the slide shows.

**One value axis + one cost axis → quadrants, not a contour. [C]** A contour says "extreme on one
axis suffices," which for a cost axis means a zero-impact trivial task outranks an important hard
one — verified at 0.717 vs 0.474 under v3's config. Impact × Effort therefore uses an explicit
quadrant split on fixed configured thresholds, with `impact / effort` ordering inside each quadrant,
and no contour math at all.

**`priority_floor: {critical: P0}` is retained.** Redundant at the shipped p = 3.0, load-bearing
under `weighted_sum` and in the `weight: 0` case Challenger found (`rubric.py:85-89`), where a
dimension override can zero a CRITICAL's derived coordinate.

### 4.4 Strategic value — derive, then allow override **[D6]**

```python
def strategic_of(finding, rubric, overrides) -> tuple[float, AxisSource]:
    if (o := overrides.get(item_id)) is not None:
        return o, AxisSource.CONSULTANT
    return rubric.weight_for(finding.dimension), AxisSource.DERIVED
```

Every row has a value; no row renders blank. The incentive inversion Challenger found in v3 — where
leaving a field empty scored *better* than answering it honestly — cannot occur, because there is no
empty state. Overrides are provenance-tagged and the render reports how many rows were overridden.

```python
class AxisSource(str, Enum):
    DERIVED    = "derived"       # computed from findings + rubric
    CONSULTANT = "consultant"    # typed by a human in the workshop
    PROPOSED   = "proposed"      # agent-suggested, unreviewed
    DEFAULT    = "default"       # config default (effort bands)
    MEASURED   = "measured"      # RESERVED — no data path, see below
```

**`MEASURED` stays reserved. [E+C]** Per-finding counts live interpolated in title f-strings and in
`CollectorResult.stats` under ad-hoc keys with no link back to the finding; building the join is the
framework bug `config.py:9-11` names.

### 4.5 Effort axis (Impact × Effort only)

Per-offering band defaults as in v2, at workstream grain. **Uncategorized CRITICALs are never
costed [C]** — verified, both demo CRITICALs have no `offering` (`ai_usage.py:133-142`), so they
collect into an **Immediate remediation** row rendering effort `n/a`. **INFO findings are excluded**
from prioritization entirely.

### 4.6 `sync` — restoring what I hollowed out **[E]**

D-6 makes per-row human data real, so this matters again. Engineer specified it in round 1 and I
reduced it to a headline. Restored in full:

- **Four arms:** unchanged item / new item / disappeared item / changed-but-matched item.
- **`status` field** on each row: `active` | `resolved` | `orphaned`. Disappeared items are marked,
  never deleted — a finding vanishing because the client fixed it is *information*.
- **Atomic write** — write to a temp file and rename, so an interrupted `sync` cannot truncate a
  workshop's notes.
- **Drop-guard:** refuse to write when a sync would orphan more than N rows without `--force`; a
  mis-pointed profile should not silently blank a filled-in sheet.
- **Join key** is `id` (§4.2), stated explicitly rather than left implied.

### 4.7 CLI

```
qba assay prioritize init   <profile.yaml> [--axes impact_effort] --out items.yaml
qba assay prioritize sync   <profile.yaml> items.yaml
qba assay prioritize render items.yaml [--weight strategic=1.5] [--shape 4] --out matrix.md
```

**[E]** `init` and `sync` currently re-run the full assessment through `run_profile`; accept a
persisted assessment as input, or state the cost in help text.

Workshop re-banding stays a first-class CLI path **[PA]** — but note that under §4.3 the shipped
p = 3.0 puts a lone CRITICAL at 0.794, so `--shape` below ~2.5 will start relying on
`priority_floor`. The render warns when the active shape sits under the crossover.

## 5. The agentic half

`AxisEstimator` Protocol with a zero-cost `DefaultEstimator` fallback, mirroring the proven
`Narrator` seam in `assessor.py`. Runs under the harness at narration's call-site pattern, declares
a `Tier.MID` ceiling via `harness/model_policy.py`, emits everything tagged `PROPOSED`, never
overwrites a `CONSULTANT` value, and writes a proposal the consultant diffs rather than a direct
write.

Its best job is unchanged from v3 and gets better under D-6: proposing **dimension weights** from
the client's own written strategy — grounded in the documents Phase 4's RAG-backed document-evidence
collector already plans to ingest. Six weights sourced from a client's Q3 charter is a citable,
reviewable artifact; thirteen per-row guesses were not. Sequence it after that collector.

**HITL remains struck from v1. [E]** `hitl_checkpoint` and `ApprovalTransport.request_approval` are
both `async` (`hitl.py:55,90`); Assay is synchronous throughout and no `ApprovalTransport`
implementation exists in-repo.

## 6. The latent bug — ship independently **[E+C]**

`report.py:113-116` ranks the roadmap by `-sum(deduction_for(severity))`, omitting dimension weight,
while `overall_score` (`rubric.py:76-90`) applies it. Real; `profile.py`'s own docstring example
(`weight: 2.0`) triggers it. It is a **3-line standalone change with two callers**, not a
"unification" — rows render in registry order (`report.py:61`) so there is no scorecard *ordering*,
and `overall_score` is a weighted mean of scores, not a sum of weighted deductions.

**D-6 raises the stakes on this.** Dimension weight now drives the strategic axis, so a roadmap that
ignores it will disagree with the matrix in the same document — exactly the hazard §4.4 forbids.
Still needs David's call **[A11]**, but it is no longer optional cleanup.

## 7. Sequencing

| Piece | Blocked by | When |
| --- | --- | --- |
| Roadmap ranking weight fix (§6) | [A11] | **Now, standalone** |
| `Finding.key` + 4 collectors + tests | nothing | **First** — everything else joins on it |
| `prioritization:` flat config + merge block | nothing | Before Phase 3 |
| `prioritize.py`: `Item`, `AxisSource`, two `AxisSet` constants, `PowerMean`, `Quadrant`, banding | above | same |
| `sync` with all four arms, status, atomic write, drop-guard | `Finding.key` | same |
| Challenge→dimension map (§3) | nothing | same — Tier 0, no code |
| `qba assay prioritize init / sync / render` | above | same |
| `AxisEstimator` + `DefaultEstimator` | nothing | same |
| LLM estimator for dimension weights | `[D3]`; **better after** Phase 4 doc-evidence collector | Phase 4 |
| Client-facing render | D-3 v2 | Phase 4 |
| Standalone task lists + Jira | second adapter | Phase 4 |
| HITL accept gate | needs sync transport or async Assay | v2 |
| Calibration from closed engagements | RAG precedent corpus | Phase 5 |

**Size, honestly, third attempt.** I estimated ~500–700 (v2) and ~800–1000 (v3); Engineer costed v3
at ~1600–2100. v4 cuts the registry (−250 to −400) but adds `Finding.key` with four collectors and
their tests (+150), full `sync` (+200), and two combination strategies instead of one (+80).
**Estimate ~900–1200 including tests**, and I would rather be told that is still low now than
discover it in build. The cheapest honest cut is dropping `impact_effort` from v1 — but that
contradicts D-5, so it is David's call, not mine.

## 8. Open decisions

- **[A8] Calibration.** Band thresholds, `shape`, and effort defaults are uncalibrated — `[A3]`'s
  problem on new axes. Absolute normalization (§4.3) is what makes cross-engagement calibration
  possible later. Do not quote externally until closed.
- **[A10] Sync conflict policy.** When a re-run's derived strategic value contradicts a stored
  `CONSULTANT` override: keep silently / keep and flag / prompt. Leaning: keep and flag.
- **[A11] Roadmap ranking weight (§6).** Now consequential rather than cosmetic. Needs David's call.
- **[A13] Prior-art provenance.** Curvature is confirmed **[D7]**, but whether the methodology was
  *used* and *worked* is still unverified. Gates `default_axis_set` only.
- **[A14] `impact_confidence` as a third set. [C]** Deferred, and cheaper than v3 implied only if
  `EvidenceType` (`findings.py:49-59`, three labels, no numbers) gets a value map.
- **[A15] Override granularity.** D-6 allows per-row strategic overrides. Should a consultant also
  be able to override *urgency*? Leaning no — severity is the deterministic spine, and letting it be
  hand-edited is where the "findings are facts" property actually breaks.

## 9. Risks

| Risk | Severity | Mitigation |
| --- | --- | --- |
| `sync` destroys workshop data | **High** | `Finding.key` (§4.2) + four-arm merge, atomic write, drop-guard (§4.6) |
| Model output launders into facts | High | `AxisSource` + `PROPOSED` never auto-accepted + renderer flag |
| Output is a severity sort in disguise | **High** *(killed v3)* | D-6 gives strategic real independent signal from client-set weights; render reports derived-vs-override counts so a run with zero client input is visible as such |
| Contour applied to a cost axis | High → **mitigated** | Quadrants for value×cost (§4.3) |
| Absolute maxima wrong ⇒ everything clusters | Medium *(new)* | Declared per-axis; validate at config load, warn if >80% of items land in one band |
| Size estimate low again | Medium | Third estimate stated with its history (§7) |
| Scope creep past `[A4]` read-only | None | Prioritizing recommends; it does not fix |

## 10. Not adopted

- **"Print the grid, record where the room places the dots" (~200 lines) [C].** Genuinely faithful
  to the slide's stated use, and the cheapest thing that could work. Rejected because D-1 and the
  original ask want the tool to *propose* a ranking from findings, not just host a whiteboard — but
  it is the right fallback if v4 proves over-built, and §4.7's render already produces the grid it
  would need.
- **Per-item strategic with unset rows excluded [C].** Superseded by D-6's hybrid, which removes the
  empty state entirely rather than special-casing it.
- **Axis registry [A, v3].** Cut per Engineer; §4.1 keeps two constants.
