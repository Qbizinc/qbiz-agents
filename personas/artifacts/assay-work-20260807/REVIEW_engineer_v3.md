# Engineer review — `PRIORITY_MATRIX_PLAN.v3.md` (round 2)

*Reviewer: Engineer. 2026-08-07. **[V]** = checked in the code. **[I]** = inference.
Round-1 review of v1 is `REVIEW_engineer.md`; I have not read the Challenger's draft.*

---

## Bottom line

v3 is a better design than v1 — the contour math genuinely retires the median-split machinery, the
§7 corrections were taken verbatim, and `MEASURED`/`ruamel`/HITL were all handled straight. But the
axis registry is **speculative generality**, for a reason the plan doesn't consider: configurability
stops exactly where the cost is. `from: severity` and `from: impact_of` are dispatch keys into a
code-side resolver table, so a new *derived* axis is always code — which makes "adding a client's own
house axes is a config block, no code" false, and makes [A14]'s "nearly free" false too. Worse, under
the shipped baseline the two axis sets the registry exists to hold are **arithmetically identical on
their derived halves** (`impact_of` = deduction × 1.0 = `urgent`, all baseline weights are `1.0`
[V]), so the registry's first two instances differ by a boolean and two label strings. Meanwhile
§4.2's derived-grain rule does **not** dissolve the `Task.id` problem — it relocates it onto the
*default* axis set and then cites itself as the mitigation for the plan's top risk; at finding grain
the only non-churning key tuple available today (`dimension, offering, subject`) **collides between
two live dbt findings** [V]. §4.3's normalization is unspecified in the one way that decides whether
the tool is stable across re-runs, and its `shape ≥ 2` claim is arithmetically wrong (needs p ≥ 2.41);
the same contour applied to Impact×Effort makes a zero-impact trivial task a P0. The ~800–1000
estimate is off by roughly 2×; my number is **~1600–2100 incl. tests**, and §8's named escape hatch
both keeps the expensive half and contradicts settled D-5.

---

## 1. The central question: the registry is speculative generality. Here is the cut.

**Verdict: cut it, keep the combination layer.** Three reasons, in order of force.

**(a) [V] The registry doesn't generalize the part that costs money.** §4.1 declares
`urgent: {source: derived, from: severity}` and `impact: {source: derived, from: impact_of}`. `from:`
is a *string naming a Python callable* — `severity` reads a field, `impact_of` is the function §4.4
defines. So `axis_sets:` is a plugin registry whose plugins live in code. §4.1's claim that "adding
Challenger's `impact_confidence` — or a client's own house axes — is a config block, no code" is
therefore only true when the new axis reuses a shipped resolver. `impact_confidence` does not:
`EvidenceType` (`findings.py:49-59`) is a three-member label enum with **no numeric ordering** [V], so
that axis needs an `EvidenceType → float` mapping written somewhere. §4.1's schema has no construct
for one. §9 [A14]'s "nearly free — `EvidenceType` already carries confidence" is wrong: it carries a
*label*, not a number. The only genuinely-different third axis set on the table needs code under the
registry too.

**(b) [V] The two shipped sets are not two instances.** `impact_of` = `deduction_for(severity) ×
weight_for(dimension)` (§4.4, signature verified — `config.py:79`, `config.py:70`). Every dimension
in `config/qbiz_baseline.yaml` is `weight: 1.0` [V], so under the shipped config `impact_of` is
*exactly* `deduction_for(severity)` — the same function `urgent` uses. The two axis sets differ in:
the human axis's label and default table, `requires_scope: true`, and `quadrants:`. That is a
boolean and two strings. They diverge only when a profile reweights a dimension, which is one
`weight_for` call, not a registry.

**(c) [I] The Phase-2 analogy does not carry.** `ASSAY_PLAN.md:292-298` genericized *before* the
second collector was written, with a stated acceptance test — "an out-of-list domain lands at
documented Tier-1 effort" (`ASSAY_PLAN.md:238-240`) — because a queue of future instances existed
and an **external party** (a client adding their own dimension) had to be able to add one without us.
Neither holds here: the population is two, both authored by us, both settled by D-5, and no client
has ever asked for a third. Genericizing before instance #2 is the Phase-2 move; genericizing *at*
instance #2 with no #3 in sight is a different trade wearing the same words.

**What I would ship instead.** Keep `combine`, `weight`, `shape`, `bands`, `priority_floor`,
`quadrants` (present/absent), `default_axis_set`, and the human axis's defaults as config — that half
pays for itself, because §4.6's live re-banding is a real requirement traceable to the prior art
("flexibility to work with client based on their feedback", `PRIOR_ART` §text). Move `axis_sets`
itself into `prioritize.py` as two frozen `AxisSet` constants next to their resolvers. Config then
overrides a *named* set's tunables but cannot declare a new one, so the `prioritization:` YAML stays
**flat** — one merge block in `apply_overrides`, same shape as `severity_weights` — instead of a
two-level nested merge (see §5 below, where most of the saving is).

**What is lost:** a client cannot invent an axis set from YAML alone. They cannot do that under §4.1
either, per (a) — a new derived axis needs a resolver. So what's lost is the *appearance* of the
capability, not the capability. When [A14] lands, `impact_confidence` costs a ~15-line constant plus
an `EvidenceType → float` map — which is what it costs under the registry too, plus the map.
**Saving: ~250–400 lines including tests**, concentrated in the config validators and the nested
merge, which are the fiddliest tests in the feature.

**§8's named cut is the wrong one.** "Ship `urgent_strategic` only, keep the registry shape, skip the
second axis set" keeps the expensive part and drops the cheap part — under (b), the second axis set
is a constant and an effort-defaults table. It also **contradicts D-5**, which is settled: both sets
ship. That escape hatch is not available, so §8 currently has no fallback at all.

---

## 2. [V] §4.2's derived-grain rule does *not* dissolve the id-stability problem — it moves it onto the default

§4.2 claims it "resolves the `Task.id` stability problem both reviewers raised **[E+C]** without
touching `Finding`", and §10 names "Derived-grain stable ids (§4.2)" as the mitigation for the
highest-severity risk in the plan. Both are false at finding grain, which is the grain of
`default_axis_set: urgent_strategic`.

The claim is that "at finding grain, ids only need to be stable *within* an axis set that never
re-groups." That is not the requirement. The requirement comes from §4.6: `sync` re-runs the
assessment and merges — so a stored item must be matched to a **freshly produced** `Finding` across
runs. `Finding` has no id (`findings.py:71-78`), and:

- **Titles churn on exactly the re-run `sync` exists for.** `dbt.py:147`
  `f"Test coverage is {test_cov}% ({len(untested)} of {total} models untested)"`; same at
  `dbt.py:162`, `:178`, `:199`.
- **Severity churns.** `dbt.py:146` `Severity.HIGH if test_cov < 50 else Severity.MEDIUM`; same at
  `:161`, `:176`.
- **`subject` is `None` on all four dbt findings** (`dbt.py:143-155`, `:157-170`, `:172-192`,
  `:194-207` — no `subject=` argument). Airflow and ai-usage do set it (`airflow.py:175`,
  `ai_usage.py:141`), so it is available on some collectors and not others.
- **`collector_name` is not on `Finding`.** It lives on `CollectorResult.name`
  (`collectors/__init__.py:52`) and is discarded when the engine flattens (`engine.py:204`).

That leaves `(dimension, offering, subject)` as the only non-churning tuple — and **it is not
unique**: `dbt.py:143` (test coverage) and `dbt.py:195` (source freshness) both emit
`dimension="data_quality"`, `offering="dbt_startup_kit"`, `subject=None`. Two live findings, one key.
Verified against the shipped demo, where both appear in the same run
(`demo/out/REPORT_acme.md`, roadmap group 1).

So at finding grain, ids today are neither stable nor unique. The round-1 fix — a `key: str` on
`Finding` that each collector sets to a count-and-severity-independent slug — is still the only
answer, and it still costs what it cost: ~80 impl + ~180 test churn across four collectors,
`TEMPLATE.py`, and their ~1,050 test lines [V: `wc -l` on `assay/tests/`].

**This is the round-1 finding that was dropped without a counter-argument** (see §3). And v3 made it
worse than v2: v2 regrained universally to workstreams, where the id *is* the offering id and the
problem genuinely evaporates. v3 makes the default the grain that has the problem.

**Compounding hazard [I]:** §9 [A13] admits the prior-art slide proves only that the method was
*presented*, and that this "gates `default_axis_set`, nothing else." That is understated. The default
axis set determines the derived grain, which determines whether the merge machinery has to survive
unstable ids at all. If [A13] resolves to "we never used it," the default flips to `impact_effort`,
grain flips to `workstream`, and the hardest half of the test surface changes shape. **Close [A13]
before build starts**, not during.

---

## 3. Round-1 handling: mostly honest, two real omissions

| Round-1 finding | v3 handling | Verdict |
| --- | --- | --- |
| #3 §7's fix described in non-existent code | Adopted verbatim in §7, incl. "not a unification," "3-line change, two callers," and the design-question reframe → [A11] | **Honest** |
| #5 `MEASURED` not implementable | §3 marks it reserved with both blockers restated | **Honest** |
| #6 `ruamel` = third dependency | §4.6 cuts it, credits [E] | **Honest** |
| #7 HITL is `async`, Assay is sync, no transport exists | §5 restates the verified facts; §8 parks it "v2, not before" | **Honest** — better than asked |
| #11 `init`/`sync` silently re-run `run_profile` | §4.6 carries it as an [E] callout | **Honest** |
| #1 quadrant/median machinery | §4.3 replaces it with contours; §11 says "adopted in substance" | **True** — but see §4, the set-relative statistic may be back, unstated |
| #2 `apply_overrides` is bespoke, not free | §8 now has its own row for "config section + merge block + validators" | **Adopted in name** — see §5, it isn't costed |
| #12/#13 sizing | §8 quotes my numbers accurately | **Honest reporting, wrong conclusion** — see §6 |
| **#4 stable `Finding` key** | Asserted away by §4.2; **no row in §8, not in §11's not-adopted list** | **Dropped** |
| **#1 "no second axis on run 1"** | Not addressed; reproduced under the new default | **Dropped** |
| **#9 `offering_total` arithmetic** | Silently gone; §4.5 says the effort table is "unchanged" | **Dropped** |
| **#10 sync merge: 4 arms, `status` field, atomic write, drop-guard** | Headline kept, all four mechanisms gone; `Item` still has no `status` | **Hollowed** |

The three that matter:

**#4 (id stability).** Covered above. This is the only one where the plan claims to have *solved*
something it hasn't, and it is load-bearing for the top risk row.

**#1 (the second axis doesn't exist on run 1).** Round-1's point was not cosmetic — it was that a 2D
instrument whose second axis is a constant is a 1D instrument, and the deliverable would look broken
in front of a consultant. v3 makes this **worse, not better**: effort at least had
`defaults_by_offering` (two distinct values across the baseline catalog); `strategic` ships
**unset** (§4.5, "there is no defensible default"). So on run 1 under the default axis set, the score
degrades to `urgent` alone, `urgent` is a monotone function of a 4-value ordinal (INFO excluded per
§4.5), and the output is a deterministic relabelling of severity — which is what `report.py:113-116`
already produces. §10's risk row ("reads as low" → render `—`) addresses the cosmetic half only.
**The real rebuttal is available and the plan doesn't make it:** §0's third bullet reframes this as a
*workshop instrument* — an empty axis you fill in the room with the client is the point, not a
defect. Say that explicitly in §4.5, because otherwise the first person to run `init` sees a severity
list and concludes the feature doesn't work.

**#9 (roll-up arithmetic).** Dropped in the version where it matters *more*. Under `impact_effort`,
grain is `workstream` — so the row **is** the roll-up, and its effort value has to be an aggregation
of per-item bands. §4.5 says the v2 defaults table is "unchanged" (i.e. `per_item` + `overhead`
survive) but nothing says what a workstream's effort *renders as*. That is now a required output, not
a deferred nicety.

---

## 4. [V/I] §4.3's contour math: formula fine, normalization undefined, two errors

**The formula is correct.** `(Σ wᵢxᵢ^p)^(1/p) · (1/Σwᵢ)^(1/p)` = `(Σwᵢxᵢ^p / Σwᵢ)^(1/p)`, the weighted
power mean. `p=1` → weighted arithmetic mean → straight boundaries ✓. `p→∞` → `max` → right-angle
contours ✓. The superellipse shape at `p≈2.5` matches the slide's description
(`PRIOR_ART`, "roughly horizontal on the left … falls steeply as it approaches the right edge") ✓.
Implementable in ~10 lines.

**Error 1 [V]: "`shape ≥ 2` clears P0 on its own" is arithmetically wrong.** With two equal-weight
axes, urgent = 1.0, the other at 0: `score = (1/2)^(1/p)`. At **p = 2 that is 0.707 → P1**, not P0.
The threshold is `p ≥ ln(0.75)/ln(0.5)`⁻¹ = **2.4094**. The shipped 2.5 clears 0.75 by 0.0079 —
a margin so thin it is an accident, not a design. And the very first thing §4.6's workshop mode lets
a consultant do breaks it: `--weight strategic=1.5` gives `(1/2.5)^0.4 = 0.693 → P1`. **A CRITICAL
silently drops out of P0 the moment anyone re-weights in front of a client.** So §4.3's "document
that [`priority_floor`] is unnecessary under the default shape" is wrong twice over: it is necessary
under any shape below 2.41, and under *any* shape once weights are touched. Make the floor
unconditional, or make the CLI refuse weight overrides that would demote a CRITICAL.

**Error 2 [I]: the contour is the wrong shape for `impact_effort`, and §4.1 applies it anyway.** The
prior-art slide has **no effort axis** (`PRIOR_ART`: "Neither axis is effort, cost, or size. Both are
value/priority-style axes"). The whole point of `p > 1` is "extreme on one axis alone is sufficient."
On Impact × inverted-Effort that reads: *a trivially cheap task with zero impact is sufficient for
P0.* Concretely, impact = 0, `invert: true` effort at band `low` → 1.0, p = 2.5 → **0.758 → P0**.
Yet §4.1 ships `combine: {fn: power_mean, shape: 2.5}` on **both** sets. Impact×Effort wants `p=1` at
most (or a ratio, which is what round-1 recommended and what the quadrant idiom actually means).
This is the generality argument biting from the other side: the two sets need materially different
combine functions, which is a per-set constant, not a shared default.

**The real gap: "normalize each axis to 0–1" is never defined**, and the two readings behave
completely differently:

- **Set-relative (min–max across items):** `ZeroDivisionError` on a single item and on all-equal
  values — the *exact* degenerate cases that got v1's median split cut (§4.4 of v1, round-1 #1),
  reimported silently. Worse, it makes bands non-comparable across runs: after the client fixes the
  worst item, the next-worst renormalizes to 1.0 and gets **promoted to P0**. For a tool whose
  headline verb is `sync`, that is disqualifying.
- **Absolute (against a declared max):** needs a max per axis. For `urgent`, that is
  `max(severity_weights.values())` — but severity weights are config (`qbiz_baseline.yaml`), so a
  profile that sets `critical: 100` shifts every band. For `impact` = deduction × dimension weight,
  the max is **unbounded** (`weight` is an arbitrary float, `config.py:36`).

Absolute is the right answer, but it has to be *specified*, including where the per-axis max comes
from, and the `impact` case needs an explicit clamp or a declared ceiling. This is the single largest
under-specification in v3.

**Smaller, all unspecified in §4.1/§4.3 [V]:**

- **Band labels have no numbers.** `strategic: {scale: bands, bands: [low, medium, high]}` — what
  float is `high`? Same for effort's S/M/L/XL. Normalization cannot proceed without a value map.
- **`invert: true`** — before or after normalization? (Different results if the max is declared.)
- **Two different `bands:` keys** with different meanings nested one inside the other's parent:
  per-axis ordinal labels vs. the top-level P0–P3 score thresholds. Rename one; a consultant is
  expected to hand-edit this file in a workshop.
- **`shape` needs a validator.** `--shape 0` → division by zero; negative → `0^negative`. Require
  `p > 0`.
- **Band boundaries need an inclusivity rule.** `{min: 0.25, id: P2}` and a MEDIUM at exactly
  `10/40 = 0.25` is a live case, not a hypothetical.
- **`Item.priority` and `Item.quadrant` are computed but §4.6 says the edited file is the consumed
  file.** If they round-trip through `items.yaml` a consultant will edit them and `sync` will
  overwrite. Emit them into a clearly-derived block, or don't emit them.
- **`Item` has no `status`** — round-1 #10's tombstone arm still has nowhere to land.

---

## 5. [V] Re-costing §4.1's YAML against `config.py`

Round-1's finding stands unchanged: there is no generic merge machinery. `apply_overrides`
(`config.py:196-258`) is 62 lines of bespoke per-section code — an explicit block for
`severity_weights` (212-214), one for `bands` (216-218), a hand-rolled merge-by-id loop for
`dimensions` (220-236), another for `offerings` (238-249), and a hand-built return (251-258).
`parse_config` (156-174) is the same shape. Nothing dispatches on section name or reflects over
fields.

**Two mechanical consequences the plan should name:**

1. `AssessmentConfig` is `frozen=True, slots=True` (`config.py:83`). A `prioritization` field needs a
   default so no construction site breaks — fine. But `apply_overrides` **hand-builds its return**
   (`config.py:251-258`), so any field not explicitly listed there is silently dropped on every
   profile load. Easy to fix, easy to miss, and it fails silently: a profile's `prioritization:`
   override just… doesn't apply.
2. **Good news, correctly free:** `profile.py:163` passes the *whole* profile mapping to
   `apply_overrides`, so `prioritization:` in a profile flows through with zero plumbing once the
   merge block exists.

**Cost of the nested version (§4.1 as written):** a *third* merge semantic in that function, at two
levels — merge `axis_sets` by set-id, then within each set merge `axes` by axis-id, then decide
replace-vs-merge for `bands:` (list), `quadrants:` (list), and `combine:` (mapping) independently.
Plus `AxisSpec`/`AxisSetSpec`/`BandSpec`/`PrioritizationConfig` dataclasses, parsers with the same
raise-on-malformed discipline as `_parse_bands` (`config.py:128-137`), cross-validators (`from:`
resolves to a registered resolver; `grain` omitted-vs-stated consistency with `requires_scope`;
`default_axis_set` names a declared set; band ids unique and one at `min: 0.0`; `weight` numeric;
`quadrants` length 4), and accessors.

**Re-cost: 170–220 lines in `config.py` + 150–200 test lines.** For calibration, `test_config.py` is
**167 lines total** covering all four existing sections [V], so this section alone roughly doubles
that file.

**Flat version (§1's cut): 70–90 impl + 60–80 test.** That is the ~250-line saving, and it is the
easiest 250 lines to save in the plan.

---

## 6. [V/I] §8's ~800–1000 is off by roughly 2×, and it is internally inconsistent

§8 quotes my round-1 numbers correctly (1400–1800 for v1 as written, ~600–700 cut) and then asserts
v3 at 800–1000. Those cannot both be true, because **v3 is strictly larger than v1 in feature
surface**. Relative to v1, v3 *removes* only the median/quadrant machinery (round-1 costed it at
150 impl + 200 test = ~350) and *adds*: the axis registry, a second axis set, derived-grain logic and
two adapters, per-set quadrant decoration, the workshop CLI overrides, the renderer refusal
mechanism (§3), and the uncategorized-CRITICAL row (§4.5). 1800 − 350 + all of that is not 1000.

| Piece | v3 impl | v3 test | Note |
| --- | --- | --- | --- |
| `prioritization:` config + nested merge + validators | 170–220 | 150–200 | §5 |
| `prioritize.py` core: `Item`, `AxisSource`, resolvers, normalize, `power_mean`, banding, floor, grain rule | 150–200 | 180–250 | contour + both sets + degenerate cases |
| `Finding → Item` adapters, two grains, INFO exclusion, uncategorized-CRITICAL row | 70–100 | 80–120 | |
| **Stable `Finding.key`** | **80** | **180** | **not in §8 at all**; see §2 |
| YAML emit + `sync` merge | 200 | 250 | unchanged from round-1; finding grain makes it harder |
| Markdown render (+ unset count, `—`, optional quadrant) | 90 | 80 | |
| CLI: 3 subcommands + `--axes/--weight axis=v/--shape` parse & validate | 70 | 70 | argparse nesting itself is ~25 (`cli.py:71-95`) |
| `report.py` internal-only refusal mechanism (§3) | 20 | 40 | touches a 431-line test file |
| `AxisEstimator` + `DefaultEstimator` | 40 | 40 | |
| §4.7 engagement-categories rubric override | 0 | ~40 (data) | **correctly priced as Tier 0** ✓ |
| **Total** | **~890–1020** | **~1070–1270** | **~1960–2290** |

**Honest number: ~1600–2100 including tests** if the `Finding.key` work is treated as required (it
is, at finding grain); **~1300–1700** if you ship workstream grain only and genuinely avoid it. With
§1's registry cut applied to either: knock off ~250–400.

Two more inconsistencies worth fixing in §8: the "~600" fallback is *below* v2's 500–700 top end
while explicitly retaining the registry that made v3 bigger than v2 — arithmetically impossible; and
§8 has no row for `Finding.key`, the renderer refusal mechanism, or the workstream effort roll-up.

---

## 7. [V] Things v3 says about this code that are wrong

1. **§0: "v2's hardcoding was a direct violation of Assay's own core design rule, stated at
   `config.py:9-11`."** Read the rule: *"If adding an assessment **domain** requires editing
   `engine.py`, `rubric.py`, or `report.py`, that is a framework bug."* It names three specific core
   files and one specific extension move — adding a domain (dimension/offering/collector). Choosing
   between two axis sets inside a **new module that does not exist yet** is neither. Invoking
   `config.py:9-11` to justify the registry is a misapplication of the rule, and since that
   misapplication is §0's entire warrant for the redesign, it should not stand as written. The
   registry may still be right — argue it on D-5 and on the workshop requirement, not on this rule.
2. **§4.3 cites `rubric.py:85-89` for the `weight: 0` hazard.** Those lines are `overall_score`'s
   zero-*total*-weight fallback [V] — unrelated. The hazard is `weight_for` returning `0.0`
   (`config.py:70`, field at `config.py:36`) zeroing `impact_of`'s product. Also: it only exists on
   `impact`. `urgent` reads severity directly (§4.4), so under the **default** axis set the hazard
   the floor is said to guard does not exist. The sentence implies a general guard.
3. **§4.1: "Adding … a client's own house axes is a config block, no code."** False for any derived
   axis — see §1(a). True for a human axis. Split the claim.
4. **§9 [A14]: `impact_confidence` is "nearly free — `EvidenceType` already carries confidence."**
   `EvidenceType` (`findings.py:49-59`) carries three *labels* with no numeric ordering [V]. It needs
   a value map that §4.1's schema cannot express.
5. **§4.2: "at workstream grain the id is the offering id, stable across re-runs by construction."**
   True as far as it goes ✓ — but note `report.py:104-107` only groups findings **that have an
   offering**, and §4.5's own uncategorized-CRITICAL row exists precisely because some don't
   (`ai_usage.py:132-142` [V] — both demo CRITICALs, confirmed in `demo/out/REPORT_acme.md:44-45`).
   That synthetic row's id needs to be reserved and stable too; it is the one workstream not derived
   from the offering catalog.

**Verified as correct in v3, for the record:** §4.4's `impact_of` body and both signatures
(`config.py:70`, `config.py:79`); §5's HITL facts (`hitl.py:55`, `hitl.py:90` both `async` [V]); §6's
corrections (`harness/src/qbiz_harness/{hitl,model_policy}.py` present, `mcp/mcp_jira/` present [V]);
§7's bug and both round-1 corrections (`report.py:113-116` vs `rubric.py:76-90`, `report.py:61`
iterating in registry order [V]); §4.5's uncategorized-CRITICAL claim [V]; §4.7's Tier-0 pricing.

---

## 8. What I would build, concretely

1. §7's ranking fix, standalone, pending [A11]. Unchanged from round-1.
2. **Close [A13] first** — it decides the default grain, which decides how hard the merge is (§2).
3. `Finding.key` — required at finding grain, and cheap to do now, expensive after four more
   collectors exist. Put it in §8 as its own row with the ~260-line blast radius.
4. `prioritization:` as a **flat** config section; two `AxisSet` constants in `prioritize.py` with
   their resolvers alongside. Config tunes weights/shape/bands/floor/quadrants/defaults.
5. Specify absolute normalization with a per-axis declared max, band-label→float maps, `invert`
   ordering, `shape > 0` validation, and band-boundary inclusivity.
6. Per-set combine defaults: `power_mean p=2.5` for `urgent_strategic`, **`p=1` for
   `impact_effort`** (§4).
7. `priority_floor` unconditional, not "documented as unnecessary."
8. YAML emit + `sync` merge with round-1 #10's four arms, `Item.status`, temp-file-and-rename, and a
   code-path assertion that refuses to drop a `consultant` value. Write these tests first.
9. Markdown render, CLI, `DefaultEstimator`, §4.7's category override.

Defer: the registry, `impact_confidence`, the LLM estimator, clustering, HITL.

**What that loses:** a client cannot declare an axis set in YAML — which §4.1 cannot actually deliver
either. And when the third set arrives, it costs a constant plus a resolver, the same as it would
have. I think that is the whole bill.
