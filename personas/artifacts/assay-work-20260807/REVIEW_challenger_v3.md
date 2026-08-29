# Challenger review — PRIORITY_MATRIX_PLAN.v3

*Reviewer: Challenger. Round 2. 2026-08-07. Against `PRIORITY_MATRIX_PLAN.v3.md`, diffed against
`v1`, checked against my own `REVIEW_challenger.md`, `PRIOR_ART_urgent_strategic.md`, and verified
against `assay/src/qbiz_assay/`, `assay/demo/out/REPORT_acme.md`, `assay/ASSAY_PLAN.md`,
`docs/USE_CASES.md`. D-1…D-5 treated as closed; nothing below re-argues them. I have not read
`REVIEW_engineer.md`.*

**Legend:** **[V]** verified in code, in the documents, or by arithmetic I ran. **[I]** inference.

---

## Bottom line

Four of my round-1 findings were genuinely fixed (median split, `ruamel`, INFO, internal-only as
mechanism, `MEASURED` reserved) and the plan is better for it. But the two central ones were
*absorbed, not answered*. "The second axis is our own price list" was answered by making the price
list optional and non-default — the mechanism is untouched (`defaults_by_offering`, "v2's table,
unchanged"), and the new contour shape gives it **more** leverage than the 2×2 did, because
"extreme on one axis is sufficient" now applies to an axis that is a cost, so *cheap* alone
promotes a zero-impact item to P1 [V]. And the new default axis set doesn't produce a second axis
at all: with `strategic` shipped unset, I ran the 13 findings in `REPORT_acme.md` through §4.3's own
formula and the entire output is **P0 = the two CRITICALs, P1 = all six HIGHs, P2 = all four
MEDIUMs, P3 = the LOW** — a verbatim relabeling of the severity column, produced by ~800–1000 lines
of registry, power-mean, merge protocol, and CLI [V]. Round 1 I called it a coin flip with a chart
around it; v3 is the severity ladder with a chart around it. Worse, the mitigation *is* the defect:
because an unset axis degrades to the derived axis alone, **saying "not strategic" demotes a row and
saying nothing preserves it** — a HIGH marked low-strategic drops to P2 while the HIGH nobody got to
stays P1 [V]. The instrument rewards silence and punishes judgment, in a room whose entire purpose
is eliciting judgment. Meanwhile §4.3's claim that contours make the severity floor redundant is
arithmetically false (`p* = 2.409`, not 2; the default 2.5 clears P0 by 0.008), the floor is still
in the shipped default config, and **the plan's own example CLI line in §4.6 makes it fire** [V].
The alternative still nobody has listed, three drafts in, is the one my round-1 objection actually
implied and which the prior-art slide's own left column hands you: **the human axis does not have
finding grain.** Effort is a property of a set; strategic value is a property of a business theme.
Ask the client to rank six dimensions once, in `rubric.dimensions[].weight`, which exists today —
instead of asking a consultant for thirteen dropdowns that answer a question nobody has thirteen
opinions about.

---

## 1. On the default axis set, the whole feature outputs the severity column [V]

I ran §4.3's formula over the 13 findings in `demo/out/REPORT_acme.md`, with the shipped severity
weights (40/25/10/4/0), §4.1's default `urgent_strategic`, §4.5's "ship `strategic` unset," §4.5's
"score degrades to the derived axis alone," and §4.1's bands (0.75/0.50/0.25/0.0):

| Band | Count | Contents |
| --- | ---: | --- |
| P0 | 2 | both CRITICALs (urgent 1.000) |
| P1 | 6 | every HIGH (0.625) |
| P2 | 4 | every MEDIUM (0.250) |
| P3 | 1 | the LOW (0.100) |

The bands are a bijection with `Severity`. `power_mean`, `shape: 2.5`, the axis registry, the
normalization step, and the contour geometry contribute exactly zero bits on our own flagship demo
in its default configuration. The chart is one-dimensional: every dot sits on the y-axis.

This is not an edge case, it is the specified out-of-the-box behaviour, and it will be what a
consultant sees the first time they run `prioritize init`. Whether it ever becomes a matrix depends
entirely on a human typing 13 values by hand, which is precisely the work the tool was supposed to
support rather than require.

Note what §8 offers as the safety valve: *"the cut is: ship `urgent_strategic` only… (~600)."* That
cut ships ~600 lines whose deterministic output is `sorted(findings, key=severity)`.

**Ask:** run this arithmetic before writing code, exactly as in round 1. If the default
configuration's output is order-isomorphic to the severity sort, the deliverable is a rendering
feature, and should be costed and sequenced as one.

## 2. §4.5's unset axis is not mitigated — it inverts the incentive in the room [V]

§10 lists this as a new **High** risk and calls it mitigated by "renders `—`, never `0`; degrades to
the derived axis; render reports unset count." Run the degradation rule against the fill-in rule
(shape 2.5, equal weights). What a row scores depends on whether the consultant *answered*:

| Row | left unset | answered "low" | answered "high" |
| --- | --- | --- | --- |
| CRITICAL | 1.000 → **P0** | 0.758 → P0 | 1.000 → P0 |
| HIGH | 0.625 → **P1** | 0.474 → **P2** | 0.844 → **P0** |
| MEDIUM | 0.250 → **P2** | 0.190 → **P3** | 0.767 → **P0** |
| LOW | 0.100 → **P3** | 0.076 → P3 | 0.759 → **P0** |

Three consequences, all fire in a live workshop:

1. **Answering costs you.** Every row the room discusses and judges unimportant drops a tier. Every
   row the room never reaches keeps its rank. The half-filled sheet isn't a cosmetic problem — the
   filled and unfilled rows are scored by **different functions**, so they are not on one ranking.
   "Half the rows are `—`" doesn't mean "half the answers are missing"; it means the visible order
   is an artifact of which rows got attention.
2. **The un-evidenced axis alone can manufacture a P0.** LOW severity + `strategic: high` = 0.759 →
   **P0**. `orders_pipeline has no meaningful owner` becomes the top-priority item in a Data & AI
   readiness report because one person picked a dropdown value. §0 sells "extreme on one axis alone
   reaches P0" as the prior art's advantage over v2. On these axes that property applies to the axis
   with *zero* evidence behind it. In `impact_effort` a bad guess could only demote; here it
   promotes anything to P0. `USE_CASES.md:9` opens with *"Every finding is a parsed fact… not an
   opinion."* This is the opinion outranking the parsed facts, by construction, in one field.
3. **Nobody can act on the render's honesty signal.** "8 of 13 rows unset" printed under a matrix in
   front of a client is not a mitigation, it is a disclosure that the instrument is not populated.

**Minimum fix if this survives:** an item with any unset axis must be **excluded from banding**, not
degraded — rendered in an "unranked" list, exactly the treatment I asked for in round 1 for
offering-less effort and which §4.5 correctly adopted there (`n/a`, never costed). v3 applies the
right rule to the axis it demoted and the wrong rule to the axis it promoted to default.

## 3. §4.3's "the floor becomes redundant" is arithmetically false, and the plan's own example
   command fires it [V]

§4.3: *"Under `power_mean` with `shape ≥ 2`, a CRITICAL (urgent = 1.0) clears the P0 threshold on
its own — the floor is redundant."*

A CRITICAL with the other axis at 0 scores `(0.5)^(1/p)`:

| p | score | band |
| ---: | ---: | --- |
| 1 | 0.500 | P1 |
| 2 | **0.707** | **P1** |
| 2.409 | 0.750 | boundary |
| 2.5 | 0.758 | P0 |
| 3 | 0.794 | P0 |

The crossover is `p* = ln0.5/ln0.75 = 2.4094`. The claim is false for `2 ≤ p < 2.41`, and the
shipped default clears the threshold by **0.008** — under 1% of the axis. That margin is the
entirety of the argument in §0 that contours are structurally better than v2's "exception-patch."

Now take §4.6's example invocation, verbatim from the plan:

```
qba assay prioritize render items.yaml --weight strategic=1.5 --shape 3
```

A CRITICAL whose `strategic` the client called low scores **0.737 → P1** [V]. `priority_floor:
{critical: P0}` is still in §4.1's default config, so it fires and relabels the row P0 — meaning the
dot plots inside the P1 region while its label reads P0, on screen, in front of the client.

§4.3 claims the contour resolves v2's "P0 means two things" problem because *"the contour **is** the
priority, and it has one meaning."* With a floor in the config, the contour is not the priority. My
round-1 finding #5 was that the floor is evidence the taxonomy is wrong; v3's answer is that the
*boundary shape* was wrong. The boundary shape changed, the floor stayed in the default config, and
the plan's own worked example makes it load-bearing. That is the objection absorbed, not answered.

**Ask:** either drop `priority_floor` from the default config and accept `p ≥ 2.5` as a hard
constraint the CLI refuses to violate, or keep the floor and delete the claim that contours made it
redundant. Both is the comfortable option.

## 4. `Task.id` stability: restated as a different problem, then declared resolved — and it is worse
   under the default [V]

§4.2 claims the derived-grain rule *"resolves the `Task.id` stability problem both reviewers raised
**[E+C]** without touching `Finding`: … at finding grain, ids only need to be stable *within* an
axis set that never re-groups."*

My round-1 finding had nothing to do with re-grouping. It was: `Finding` has no id
(`findings.py:62-79`, verified again — dimension, severity, title, detail, remediation, offering,
subject, evidence); the only candidate key is `title`; titles are f-strings with mutable counts
(`dbt.py:147` `f"Test coverage is {test_cov}% ({len(untested)} of {total} models untested)"`,
verified); severity is computed from the same number (`dbt.py:146`). The client fixes two models,
`sync` runs, the id changes, the consultant's typed value orphans. Grain does not enter into it.

v3 makes this strictly worse than v2:

- Finding grain is now the **default** (§4.1 `grain: finding`). v2's regrain to workstream genuinely
  dodged this; v3 undoes the dodge and keeps the claim of resolution.
- The human axis under the default is `strategic` — the field a consultant types **live, in a
  workshop, in front of a client**. The most expensive-to-reproduce data in the system now sits on
  the least stable keys.
- The keys are still undefined. §4.2 offers a property ids "only need" to have; it does not specify
  what the id *is*. §4.6 calls merge *"the highest-risk code in the feature"* and makes merge tests
  an acceptance criterion — for a merge whose join key does not exist in the plan.

§10 rates "sync destroys consultant-typed work" **High**, mitigated by *"Derived-grain stable ids
(§4.2)."* The cited mitigation does not exist in the default configuration. This is the most
consequential false resolution in the document.

**Ask:** name the key. `(collector_name, check_id, subject)` on `Finding` is a core change touching
every collector and is still not in §8's sequencing table or the size estimate. If that is too
expensive, the honest alternative is to keep workstream grain unconditionally and drop §4.2.

## 5. The two numbers that decide every band are unspecified [V by absence]

§4.3 says *"Normalize each axis to 0–1"* and stops. `grep -in normali` on v3 returns one line. The
basis is never given, and it is the whole ballgame:

- **Normalize by theoretical max (severity_weights max = 40):** stable, comparable, explainable.
- **Normalize by observed max:** in an estate with no CRITICALs, HIGH → 1.000 instead of 0.625, so
  *every client gets P0s*; and after a client fixes their CRITICALs, untouched rows change band on
  the next `sync` [V — arithmetic: high 25/25=1.000 vs 25/40=0.625].

That second option is my round-1 finding #6 (relative-to-self priorities kill cross-client
comparison and churn labels on re-run) reproduced exactly. v3 removed the *named* mechanism (median
split) and left an *unnamed* one with the identical property as an unmade implementation decision.
Silence here is not neutrality; it is the same defect with nobody's name on it.

Likewise §4.1's `bands: [low, medium, high]` carries **no numeric values**. A plan that specifies
`shape: 2.5` to one decimal does not say what "medium strategic" is worth, and the answer moves rows
a full tier: a HIGH with `strategic: low` is P2 at low=0.0 and P1 at low=0.33 [V]. On the plan's own
example command a CRITICAL is P1 at low=0.0 and P0 at low=0.33 [V].

**Ask:** both constants go in the config with the normalization basis named, and the render header
stamps the axis set id, shape, weights, and normalization basis. Which brings me to —

## 6. Configurability moved the failure from "one wrong number" to "an unrecorded choice" [V/I]

You asked whether "make the axes configurable" is a real answer. Partly, and here is the part that
isn't. Under D-5 the axis set is a consultant call — so it is now the single most consequential
decision in the deliverable, and **nothing in v3 requires it to appear in the artifact.** §4.6
specifies only that the render reports the unset count. Two `items.yaml` files from two engagements
are not comparable, the rendered matrix does not say why, and the audit log is not mentioned in
connection with the choice at all.

That is a new abuse surface, and per my remit the abuser is us: the same finding can be P1 or P0
depending on an unlogged flag, and the flag is picked by the person with a commercial interest in
what lands at P0. In v1 the tunable thing was an invisible day-band midpoint; in v3 it is the entire
instrument. This is the "two ways to be wrong" your framing suspected, and the fix is cheap:
**stamp `axis_set`, `shape`, weights, normalization basis, and unset count into both the YAML and
the rendered header, and into the audit trail.** One dict, no design cost.

## 7. Contours make my round-1 price-list finding *worse*, not better [V]

§4.5 keeps effort defaults as *"v2's table, unchanged."* The mechanism I objected to — `task.effort`
is a pure function of `finding.offering`, i.e. of which product we sell — is untouched. What changed
is the boundary shape, and it changed against us. With `invert: true` on effort and shape 2.5:

| impact ↓ / effort → | S | M | L | XL |
| --- | --- | --- | --- | --- |
| CRITICAL | P0 | P0 | P0 | P0 |
| HIGH | **P0** | **P0** | P1 | P2 |
| MEDIUM | **P1** | P1 | P1 | P3 |
| LOW | **P1** | P1 | P2 | P3 |
| impact 0 | **P1** | P1 | P2 | P3 |

A **zero-impact** item priced S scores 0.717 → **P1**, above a HIGH priced XL (0.474 → P2) [V]. In
v1's median 2×2 a low-impact cheap item could reach at most `fill_in` → P2. The contour's celebrated
"extreme on one axis is sufficient" property is correct for two *value* axes — the prior-art
transcription is explicit that *"Neither axis is effort, cost, or size. Both are value/priority-style
axes"* — and is nonsense when one axis is a cost. "This is cheap" is now sufficient reason to rank
something highly, and cheapness is a lookup on the Qbiz catalog. Since `dbt_startup_kit` is the S
band and covers four demo findings, the systematic effect is the same one I named in round 1, one
band stronger.

§4.1 applies the same `combine: {fn: power_mean, shape: 2.5}` to both axis sets. It should not: the
shape borrowed from a value×value slide is being applied to a value×cost pair. At minimum
`impact_effort` needs `p ≤ 1`, and a `p ≤ 1` contour is a straight-or-concave line, which is v2's
2×2 — which is the finding that the registry's second axis set has no reason to use the registry's
new machinery.

## 8. The prior art: [A13] gates the whole document, not `default_axis_set` [V]

[A13] states the caveat correctly and then contains it: *"This gates `default_axis_set`, nothing
else."* Trace what actually rests on the slide, by the plan's own **[PA]** markers: §0's entire
rationale for the redesign; §4.3's contour math and `shape: 2.5` (*"the rounded corner the
prior-art slide draws"*); §0's "workshop instrument, not a scoring engine" reframe, which is the
sole justification for §4.6's live-override CLI; §4.2's grain-derivation rule, which only exists
because a no-scope axis set exists; §4.7; and the ~300 lines of registry indirection that exist
because there are two axis sets. Remove the slide and v3 is v2. Confining its caveat to one config
key is the most comfortable sentence in the document.

Three more things about it, in descending confidence:

- **The slide's unit is not v3's unit. [V]** The transcription's own note 3: *"the plotted items are
  **recommendations** — remediation proposals — not raw findings and not tasks."* §4.1 sets
  `grain: finding` for that exact axis set. The one document that could settle the grain question
  answers it, and the plan derived the opposite. My round-1 Alternative A is recorded in §11 as
  *"partially adopted — took the grain insight"* while the default path takes the opposite of it.
- **The plan mined the wrong list. [V]** §4.7 adopts *"Data Management categories"* as a rubric
  override. The other list — *"Most significant challenges: Data Confidence / Development Velocity /
  Cost Efficiency / Security Risk"* — appears **nowhere** in v3 (`grep`: zero hits for "Most
  significant", "Data Confidence", "Development Velocity"). Four business themes, on a slide about
  prioritization, sitting immediately under the words "Based on dimensions of Urgency and Strategic
  value." The most natural reading is that *this is how strategic value was expressed* — as themes,
  not per-item scores. That reading answers §10's new High risk outright, and it was skipped in
  favour of a Tier-0 nice-to-have. See §10 below.
- **The geometry is self-contradictory and was resolved in the plan's favour. [V that it is
  contradictory; [I] on which reading is right.]** The transcription says the curves are *"convex
  toward the origin"* and, in the same sentence, that each *"runs roughly horizontal along the left
  side, then bends downward and falls steeply as it approaches the right edge."* Those are opposite
  shapes: flat-then-plunge is a superellipse with exponent **> 1**, which bulges *away* from the
  origin; convex-toward-origin is exponent **< 1**, an astroid, which is an AND gate requiring
  *both* axes high — the exact inverse of the "key geometric property" the plan builds on. §4.3
  picks `p = 2.5` without noting the ambiguity. If the real slide is `p < 1`, `shape: 2.5` is the
  opposite instrument and every P0 it emits contradicts the prior art.

And the structural point: the Architect wrote v1, transcribed the slide (*"subagents cannot be shown
the image"*), wrote the interpretation, wrote v3, and authored §11's register of which reviewer
proposals were adopted. The one piece of external evidence in this project is unverifiable by any
reviewer and passed through a single interested party. **Ask:** put the image somewhere a reviewer
can see it, and close [A13] with the person who ran the engagement, before `shape` and
`default_axis_set` are written down as defaults — which §4.1 already does.

## 9. §4.4 claims a single authority and then defines two scales two lines apart [V]

> *"One authority — the rubric — for every derived axis, so no second scale can drift from the
> scorecard."*

Directly above it: `urgent` uses severity **directly**; `impact` uses `deduction × dimension_weight`.
Those are two scales. Consequence under the **default** axis set: a profile that reweights
`governance: 2.0` moves the scorecard (`rubric.py:76-90`, verified) and does **not** move the
matrix. `USE_CASES.md:30` sells reweighting as *the* Tier-0 client-tuning move. So the tuning knob we
advertise now silently desynchronizes the two rankings in one document — my round-1 finding #4, with
a new cause and the same client-facing failure: page 4 says Governance is the most exposed
dimension, page 6 ranks a governance finding level with everything else HIGH.

Relatedly, §7 correctly keeps the roadmap-ranking weight fix independent — but until [A11] closes,
`report.py:113-116` still orders offering groups by unweighted summed deduction while the matrix
orders by contour. Two rankings, one document, still.

## 10. The alternative still nobody has listed, three drafts in

My round-1 objection to effort was not "effort is unknowable." It was **"effort is a property of a
set, not of a task"** — §4.3 of v1 invented `overhead` because of it, §5 of v1 conceded it. v3
changed the human axis and **kept the assumption that the human axis has finding grain.** Strategic
value is a property of a business theme, not of a finding. Nobody in the room has an opinion about
whether *"1 source(s) have no freshness checks"* is strategic; they have an opinion about whether
**data reliability** is strategic. Thirteen dropdowns produce thirteen answers to a question with
about four real answers, and the other nine are noise typed under time pressure and then rendered
next to parsed facts.

**Alternative D — the strategic axis has dimension grain, and the mechanism already ships.**
Ask the client once: *rank these six dimensions by business importance.* That is `weight` on
`rubric.dimensions[]`, parsed by `config.py:104-112`, merged by `apply_overrides` (`config.py:220-236`),
already the documented Tier-0 move. Then `strategic(finding) = client_weight(finding.dimension)`.

- Answers **who fills it in** — the client, once, in the kickoff conversation they are already in.
- Answers **what "Strategic" means for "4 of 6 models have no tests"** — how much this business
  depends on trustworthy data, which is a question a CFO can answer and a per-finding dropdown is not.
- **Eliminates §10's new High risk entirely.** No row can be unset; the sheet is complete the moment
  the profile is written; there is no half-filled state, no answer-vs-silence asymmetry.
- **Stable across `sync`** (dimension ids don't change when a coverage number does — which also
  drains most of finding #4) and **comparable across clients**, which the Phase-5 benchmark story in
  `USE_CASES.md:50` needs and a per-item human axis cannot support.
- **Has real provenance**: "you told us Governance was your top priority" beats "a consultant picked
  High." It is `AxisSource.CONSULTANT` with an actual source.
- Cost: a config field and one lookup. Zero new code paths. It also makes the LLM estimator in §5
  a much better-posed task — proposing six dimension weights from a client's strategy documents is
  tractable and citable; proposing thirteen per-finding strategic scores is not.
- Corroborated by the prior art's own unread list: four themes, not per-item scores (§8 above).

The honest cost: it collapses the second axis to six distinct values, so findings within a dimension
share a strategic score. That is not a limitation, it is the accurate statement of where the
information lives. If six bands is too coarse, that is an argument for more dimensions, which is a
Tier-0 config change — §4.7's engagement-categories override, which the plan already wants to ship,
gives you five more.

**Alternative E — don't compute a priority at all; print the grid and record the placements.**
§0 says, correctly, *"this is a workshop instrument, not a scoring engine."* The plan then builds a
scoring engine: a power mean, a shape parameter, band thresholds, a normalization step, an axis
registry, a grain-derivation rule, a merge protocol, and an LLM estimator — all to manufacture a
number §4.5 admits it cannot manufacture. If the axes are renegotiated live and one has no
defensible default, the artifact that matches the stated use is: findings with their derived axis, an
empty second column, a printed grid, and a recorder for where the room placed each dot, tagged
`CONSULTANT`. Renderer plus YAML round-trip, ~200 lines, ships this week, `[A8]` evaporates because
there is nothing uncalibrated to calibrate — and placements from three engagements are the only
substrate that could ever justify a scoring function later. The scoring engine is the expensive
option being treated as the obvious one because it is the familiar one; §1 of v1 said so out loud
and §1 of v3 still does.

*Both are proposals. I am not asking to build either, and D-1…D-5 hold under both — D and E live in
`qbiz_assay`, use bands, stay internal-only, and D-5's two axis sets remain selectable.*

**Also noted, not re-argued:** round-1's Alternative C (impact × prerequisite depth) does not appear
in v3 at all — not adopted, not deferred, and not in §11, which presents itself as the register of
proposals not adopted. It left the record without a ruling. I am flagging the gap in the register,
not re-making the argument.

## 11. Where v3 is telling itself a comfortable story

- **§0 convicts v2 of a framework bug to authorize the registry. [V]** It cites `config.py:9-11`:
  *"If adding an assessment **domain** requires editing `engine.py`, `rubric.py`, or `report.py`,
  that is a framework bug."* That rule is scoped to assessment domains and to three named files.
  A second axis set is not a domain, and `prioritize.py` does not exist yet, so it is not one of the
  three files. The rule was generalized to "any second instance of anything must be a registry" and
  used to justify ~300 lines of indirection at N=2, in the same document that concedes in §8 the
  trade may be wrong. Invoking the codebase's constitution against your own previous draft is a
  strong move; it should be the right clause.
- **§11's register is graded by the author of the thing being graded. [V/I]** The Architect wrote
  v1, transcribed the sole external evidence, wrote v3, and wrote the record of which reviews were
  adopted. §0 tells the reviewer where the reviewer was wrong — *"Challenger read the floor as proof
  the taxonomy was broken. It wasn't — the boundary shape was"* — on the one point where §3 above
  shows the floor is still in the default config and still fires on the plan's own example command.
  Two proposals are recorded as "partially adopted" or "adopted in substance" where the default path
  does the opposite (§8, grain) or the artifact retains the thing (`quadrants:` is still a config
  key, still a computed `Item.quadrant` field, still rendered — "adopted in substance" is doing a lot
  of work for "kept, renamed as flavour text").
- **"Size, honestly" understates the direction of travel. [V]** The redesign was triggered by a
  slide with **fewer** axes and no effort dimension, and the plan grew from ~500–700 to ~800–1000.
  A simplification in the requirements produced an increase in the build. That can be right, but it
  should be stated as what it is rather than as the Phase-2 precedent, which genericized *before*
  any second instance existed and is therefore the opposite case.
- **§5 overstates the Phase-4 synergy. [V]** `ASSAY_PLAN.md:255-265` scopes the RAG document
  collector to *policy PDFs, runbooks, data dictionaries, wiki exports, org charts*, for governance
  *process* dimensions — retention policy, escalation runbook, named owner. "Strategy decks" and
  "Q3 charter" are v3's additions, and a client's strategy artifacts are typically not in the
  artifact drop. The synergy is real in shape and thinner in substance than *"exactly the
  evidence-quality upgrade that collector exists to deliver."*
- **§10 still rates "Scope creep past [A4]" as severity None** while §8 sequences agent-created
  Jira tickets, unchanged from v1. I raised this in round 1; it was not adopted and does not appear
  in §11's not-adopted register either. It is out of v1 scope; it is not a non-risk.

---

## Credit where it's due — verified

- **The median split is genuinely dead**, and fixed thresholds on a bounded ladder are the right
  call. That was my sharpest round-1 finding and it was answered, not absorbed.
- **§4.3's power-mean formula is algebraically correct** as written, and the `p=1` / `p→∞` limit
  claims check out. The shape *does* reproduce a flat-then-plunge contour. The problems are the
  normalization basis, the threshold arithmetic, and applying it to a cost axis — not the algebra.
- **`MEASURED` reserved, HITL struck (verified: `hitl.py:55,90` both `async`, Assay synchronous),
  no `ruamel`, INFO excluded, uncategorized CRITICALs never costed** (verified again:
  `ai_usage.py:133-142` has no `offering=` on either CRITICAL) — all correct, all adopted cleanly.
- **Internal-only graduated from convention to renderer mechanism** — this was the right response
  and it is exactly the `[A4]` discipline it was measured against.
- **§7 stays independent, and its two Engineer corrections are right.** `report.py:61` iterates
  registry order, so there is no scorecard ordering to unify; `overall_score` is a weighted mean of
  scores and cannot consume `impact_of()`. Ship the 3-line fix behind [A11], separately, now.
- **§4.5's `n/a` treatment for uncosted CRITICALs is the correct rule.** Apply the same rule to
  unset `strategic` (finding #2) and the highest-severity new risk in §10 goes away.
