# Challenger review — PRIORITY_MATRIX_PLAN.v1

*Reviewer: Challenger. 2026-08-07. Against `PRIORITY_MATRIX_PLAN.v1.md`, verified against
`assay/src/qbiz_assay/`, `assay/demo/out/REPORT_acme.md`, `ASSAY_PLAN.md`, `docs/USE_CASES.md`.
D-1..D-4 treated as closed; nothing below re-argues them.*

**Legend:** **[V]** verified in code or by arithmetic over the shipped demo. **[I]** inference /
judgment.

---

## Bottom line

The engineering here is careful and the two side-catches (§7's roadmap-ranking bug, §6's corrections)
are real and worth landing on their own. But the instrument is wrong for the data. Assay's impact
axis is a five-value ladder and the effort axis is a four-value lookup keyed on *which product we
sell* — so a median-split 2D quadrant over the flagship demo's 13 findings has only 4 distinct
impact values and 2 distinct effort values, every split lands on a mode, and depending on a
tie-break convention nobody will review, the `quick_win` quadrant comes out either **empty** or
**exactly the two cheapest dbt findings** [V]. On that demo the entire P0 list is produced by the
severity floor, not by the matrix. Meanwhile the effort default is looked up per offering, which
means the "objective" chart's second axis is a restatement of the Qbiz catalog, and the number
driving it is never printed (§4.3). The deeper problem is the framing: the plan's own §4.3 (shared
overhead) and §5 (dependency clustering) both concede that effort is a property of a *set*, not of a
task — which is precisely what a scatter plot cannot represent. **The alternative nobody listed is
to estimate at the offering grain and ship a phased plan instead of a matrix** (§3 below): it is
where the plan's own defaults already live, where the Phase-5 calibration substrate actually exists,
and it is roughly a day of work on top of the roadmap section that already ships. The matrix is the
familiar shape, and §1 says so out loud — "consultants have historically ranked engagement tasks on
a Priority-vs-Effort matrix" is the entire stated justification.

---

## 1. The quadrant machinery produces ~nothing on our own flagship demo [V]

Arithmetic over `REPORT_acme.md`'s 13 findings, using the shipped `qbiz_baseline.yaml` weights
(critical 40 / high 25 / medium 10 / low 4, all dimension weights 1.0) and the plan's own §4.3
effort defaults.

**Impact values:** `40, 40, 25, 25, 25, 25, 25, 25, 10, 10, 10, 10, 4` — n=13, median = 25.
**Four distinct values for thirteen items. Six items sit exactly on the median.**

**Effort values:** `dbt_startup_kit → S(1.5)` covers 4 findings (test cov, doc cov, freshness,
retries); everything else lands on `M(4)` — `incident_agent` ×2, `agent_harness` ×2,
`sensitivity_classification` ×1, and 4 findings with **no offering at all** falling to the `fallback:
{per_item: M}`. So: `4 × 1.5, 9 × 4`. Median = 4. **Two distinct values.**

Now run §4.4:

- **Tie-break "high = strictly above median":** high-impact = the two CRITICALs only (impact 40).
  Both are the hardcoded-credential findings, which carry **no offering** (`ai_usage.py:136-137`,
  no `offering=` kwarg) → effort M(4) → *not* low-effort. **`quick_win` is empty. P0 is produced
  entirely by rule 4, the severity floor.** The matrix contributed zero.
- **Tie-break "high = at or above median":** high-impact = 8 items, low-effort = 4 items,
  `quick_win` = {test coverage, doc coverage} — both `dbt_startup_kit`. P0 = those two plus the two
  criticals by floor.

The answer flips between "nothing" and "buy the dbt kit" on a `>` vs `>=` in a helper function. That
is not a robust instrument; it is a coin flip with a chart around it.

§4.4's stated degenerate case — "n < 4, or all items in one band" — names the wrong pathology. The
real degenerate case is **ties at the median**, and on a five-value severity ladder crossed with a
four-band effort ladder, ties are not an edge case, they are the *normal* case. The plan treats the
pathology as the exception and the exception as the pathology. The proposed mitigation (fall back to
fixed thresholds below a minimum task count) does not fire here: n=13 is comfortably above any
sensible minimum.

**Ask:** before writing any code, run this arithmetic over `REPORT_acme.md` and two other assessment
outputs. If `quick_win` is empty or single-offering on all three, the quadrant is not the deliverable
§4.4 claims it is.

---

## 2. The effort axis is a lookup on our own price list [V, consequence I]

§4.3 keys effort defaults by `defaults_by_offering`. Offerings are Qbiz products
(`qbiz_baseline.yaml:57-68`). In v1 there is no per-finding effort signal anywhere — `Finding` has no
size, count, or scope field (`findings.py:62-79`) — so **`task.effort` is a pure function of
`finding.offering`.** Every `dbt_startup_kit` finding is S; every `sensitivity_classification` finding
is M; and so on, forever, until a human types over it.

Three consequences:

1. **The quadrant chart is a picture of the catalog, not the estate.** "What should you do first?"
   resolves to "whichever offering we priced cheapest." On the demo that is the dbt Startup Kit,
   every time, for every client, regardless of what the scan found. [V for the mechanism; the "every
   client" claim is [I] but follows directly.]
2. **It is silently tunable in our favour.** Move `sensitivity_classification` from M to S in config
   and it migrates into `quick_win`/P0. The `axis` midpoint is *"never rendered"* by design (§4.3), the
   day range is a band not a number, and D-3 removes any client-facing disclosure. A change to what
   we recommend a client buy first, with no visible trace in the artifact. §9's `[A8]` concedes these
   values are guesses. A guess we control, that nobody can see, that determines purchase order, is
   the most abusable surface in this design — and the abuser is us, which is the hard kind to notice.
3. **The estimate is least informed exactly where it matters most.** In the demo, all four
   offering-less findings hit the `fallback: M` — including **both CRITICALs**. The rendered artifact
   would read *"Rotate the credential now — Medium, 3-5 days."* Rotating a credential is minutes.
   That is a confidently wrong number, attached to the highest-stakes item, in the row a consultant
   is most likely to read aloud. [V: no `offering=` on `ai_usage.py:136`; band mapping from §4.3.]

**Minimum fix if the matrix survives:** a finding with no offering must not receive a defaulted
effort at all — it must render as `—` / `unknown` and be excluded from quadrant math, not silently
assigned the median band.

---

## 3. The alternative nobody listed: estimate at the offering grain, ship a phase plan, not a matrix

The plan asks "how do we add an effort axis to findings?" The prior question is **"is a finding the
right unit of estimate?"** It is not, and the plan half-knows this:

- §4.3 invents `overhead` because per-finding effort overcounts — i.e. because tasks share setup.
- §5 says the agent's real value is *"clustering findings into coherent workstreams and identifying
  sequencing dependencies"* — i.e. because tasks are not independent.
- §8's last row puts calibration on *"actual closed engagements"* — and a closed engagement is an
  **offering**, not a finding. There will never be a calibration datum for "backfill descriptions on
  four models." [V: `ASSAY_PLAN.md:374-379`, `[A3]`, and the Phase-5 precedent corpus are all
  engagement-grained.]
- §4.3's defaults are *already keyed by offering*. Per-item is a derived fiction on top of the one
  number that was actually estimated.

**Alternative A — the one I'd argue for.** Estimate per offering. Extend the roadmap section that
already ships (`report.py:104-121`) with an effort band and a phase order:

> ### Phase 1 — Qbiz dbt Startup Kit — Medium (2-3 weeks)
> Retires 4 findings (2 HIGH, 2 MEDIUM). Prerequisite for: Sensitivity Classification.

Cost: one config block (`effort_by_offering`), one column, one sort. No new module, no CLI verb
group, no YAML round-trip, no merge semantics, no id-stability problem, no estimator agent, no
accept gate. It answers the question a proposal actually asks — *what's phase 1 and what does phase
1 cost* — which a scatter plot does not. And it is honest at the grain where we have evidence.
[I, but every input is [V].]

The cost of the conventional option is what's being treated as free here: the matrix buys a picture
and charges for a subsystem — round-trip YAML merge, stable ids, provenance enum, an LLM estimator,
a HITL gate, and a second ranking to keep in sync with the first.

**Alternative B — if a second axis must exist, make it Impact × Confidence.** Assay already carries
`EvidenceType` per finding (`findings.py:49-59`) and marks unassessed dimensions honestly
(`rubric.py:61-62`). "How sure are we of this" is derivable from facts we hold; "how long will this
take" is derivable from nothing. A CRITICAL that was *parsed* and a CRITICAL that was *attested* are
genuinely different objects and the report today notes the difference but never ranks on it. This
axis is also the differentiator — every competitor's spreadsheet already claims an effort column;
none of them can show provenance.

**Alternative C — Impact × prerequisite depth.** Take §5's own insight seriously and make the second
axis "how much must happen first," computed once from the dependency graph. That yields waves for
free and is the honest answer to "why an agent here at all" — which §5 already identifies and then
declines to act on, keeping effort as the axis anyway.

*These are proposals. I am not asking to build any of them, and D-1..D-4 stand either way — A, B,
and C all live inside `qbiz_assay`, all use bands, all stay internal-only.*

---

## 4. §4.4 breaks §4.2's own non-negotiable [V]

§4.2: *"Non-negotiable: a second priority scale would put two disagreeing rankings in one
document."* §4.4 then ranks by quadrant, which is impact **and** effort. The report's roadmap ranks
by summed impact alone (`report.py:113-116`). A finding that is #1 in the roadmap can be P1 in the
matrix because it is expensive. **That is two disagreeing rankings in one document** — the exact
failure §4.2 declared closed, reintroduced two sections later, and §10 rates it "Medium — mitigated
by a single `impact_of()`." Unifying `impact_of()` does not fix it; the disagreement is the effort
term, not the impact term.

In front of a client this is the concrete failure: page 4 says Governance is the most exposed
dimension and lists the credential first; page 6's matrix files it as a Major Project. Someone will
ask which page to believe.

---

## 5. The P0 severity floor is evidence the label is wrong, not an exception to it [V/I]

Rule 4 exists because a hardcoded credential filed under "Major Project — later" would contradict
the executive summary (`assessor.py:72`, verified — though note that string is the *rule-based
fallback* narrator; an LLM narrator is not bound to say it, so the contradiction the plan is
guarding against isn't guaranteed to be visible).

But the floor makes "P0" mean two incompatible things in one column: *"high impact and cheap"* and
*"this is on fire."* A consultant sorting by P0 gets quick wins and emergencies interleaved. On the
demo that is literally a list of {rotate two credentials, add dbt tests, write model descriptions} —
a security incident and two hygiene chores, presented as one tier.

The floor is telling you the taxonomy is wrong. Exposures are not a priority band; they are a
separate section. The report's exec summary already gets this right — *"they are exposures, not
backlog."* The matrix should not put them in the backlog and then bolt on a rule to lift them back
out.

---

## 6. Median split makes P0 a percentile, and re-running silently re-labels [V/I]

A median guarantees ~half of items are "high impact" — always. So the **P0 count is a function of
how many collectors ran, not how bad the client is** [V by construction]. Two consequences the plan
doesn't address:

- **Cross-client comparison dies.** "Acme had 3 P0s, you have 6" is meaningless, but is exactly what
  the Phase-5 benchmark story promises (`USE_CASES.md`: *"you're in the bottom quartile for test
  coverage"*). A relative-to-self priority scale cannot support a relative-to-peers pitch.
- **Re-running churns priorities with no change in the facts.** Add a collector — or the client
  fixes four things — and the median moves; untouched findings flip P0→P1. §4.5 is careful to
  preserve `notes` and `consultant` effort across a `sync`, and never notices that the **P-labels
  themselves are not stable across a sync**. The consultant who mailed a matrix last month cannot
  explain in the room why item 6 dropped a tier. That is the in-front-of-a-client failure mode you
  asked for, and it is caused by the median, not by a bug.

Fixed thresholds on the impact ladder (which is bounded and known: 0-40 × weight) would be stable,
comparable, and explainable. §4.4 rejects them for a reason that does not hold: *"a set of
uniformly-critical findings should still separate."* If every finding is critical, they genuinely
should **not** separate — that is a true and important statement about the client, and forcing a
split manufactures a distinction the evidence does not support. Assay's whole credibility argument
is that it doesn't do that.

---

## 7. `impact = severity_weight × dimension_weight` conflates two different "weights" [V]

`weight` is documented in `qbiz_baseline.yaml:32-34` as *"the dimension's share of the overall
score."* In `overall_score` it is a **normalizing weight in a weighted mean of dimension scores**
(`rubric.py:76-90`). §4.2 repurposes it as a **multiplier on a per-finding deduction**. These are not
the same quantity and unifying them behind one `impact_of()` will make future readers believe they
are.

Two concrete failures:

- **`weight: 0` is an explicitly supported override** — `rubric.py:83-89` has a dedicated branch for
  it, commented *"score and report this, but don't let it move the overall."* Under §4.2 every
  finding in that dimension gets **impact 0**, including CRITICALs. Combined with rule 4 you get a
  P0 plotted at the origin of the quadrant chart: bottom-left, "low impact," labelled top priority.
  A profile that says "report governance but don't let it move the headline score" should not zero
  out the priority of a hardcoded credential.
- **Direction is unstated and non-obvious.** Doubling a dimension's weight doubles every finding's
  impact *and* doubles that dimension's pull on the overall score — the same knob now does two
  things with different curves. `USE_CASES.md` sells reweighting as the no-code client-tuning move
  (*"reweight dimensions to what the client cares about"*); consultants will turn this dial without
  knowing it moves the roadmap.

Also, §7's fix statement is slightly off: *"one `impact_of()` used by the scorecard ordering"* — the
scorecard has no impact ordering, it iterates registry order (`report.py:61`). The **bug itself is
real and correctly diagnosed** (`report.py:115` omits `weight_for`, `rubric.py:76-90` applies it);
just don't let the fix quietly redefine what `weight` means.

---

## 8. `Task.id` stability: the plan's stated worst outcome is caused by the plan's own id scheme [V]

§4.5: *"`id` stable across regeneration"* and *"Destroying a consultant's typed work is the worst
outcome this feature can produce."* Correct — and then:

**`Finding` has no id** (`findings.py:62-79`: dimension, severity, title, detail, remediation,
offering, subject, evidence). The only candidate key is `title`, and titles are f-strings with
mutable counts embedded:

- `dbt.py:147` — `f"Test coverage is {test_cov}% ({len(untested)} of {total} models untested)"`
- `dbt.py:162` — `f"Documentation coverage is {doc_cov}% ({len(undocumented)} models undescribed)"`
- `dbt.py:178-180`, `dbt.py:199` — same shape.

Worse, `severity` is itself computed from the coverage number (`dbt.py:146`, `161`, `176`), so it
moves too.

The client fixes two models. `sync` runs. `"Test coverage is 33% (4 of 6…)"` becomes
`"Test coverage is 67% (2 of 6…)"` — different id, so sync sees one task disappear and a new one
appear. The consultant's typed effort and notes orphan. **This fires on the exact event that
motivates a re-run.** And it hits the `dbt_startup_kit` cluster — the biggest offering group, the one
most likely to be annotated. The Airflow findings are safer (`subject` = dag_id, stable), so the
failure is partial and therefore easy to miss in testing.

This is not fixable in merge semantics. It needs a stable key on `Finding` — `(collector_name,
check_id, subject)` — which is a change to the deterministic-facts core touching every collector.
That work is not in §8's sequencing table and is not costed.

---

## 9. `EstimateSource.MEASURED` has no data path [V]

§3 defines `MEASURED = "arithmetic over a countable fact (4 untested models × rate)."` The count is
not available. `Finding` carries no numeric payload; the counts live in (a) the title string and (b)
`CollectorResult.stats` (`dbt.py:119-127`), which is aggregate per-collector and **not keyed to
individual findings** (`engine.py:65` — `collector_results` and `findings` are parallel lists with no
link).

So MEASURED ships as either a dead enum member or a regex over prose. Both are bad; the second is
worse, because it produces a number tagged as the *highest-trust automated* provenance tier derived
from scraping display text. The honest fix is a structured count field on `Finding` — again, a core
change, again uncosted.

---

## 10. Smaller verified misfires

- **INFO findings become costed P2 tasks.** `ai_usage.py:183-190` emits
  `Severity.INFO`, *"No direct LLM usage detected — greenfield"*, with `offering=ai_advisory`. Under
  §4.2 its impact is `0 × weight = 0`; under §4.3 `ai_advisory` per_item is S. It lands in
  `fill_in` → **P2**, appears in the matrix, and contributes to the `ai_advisory` effort roll-up. A
  finding whose content is *"you're fine"* becomes a priced backlog item. The `Finding → Task`
  adapter has no actionability filter, and there is no field to filter on other than
  `severity == INFO` (which is a proxy, not a fact). [V]
- **Overhead and the quadrant disagree.** §4.3 sets `offering_total = overhead + Σ(per_item)` but
  §4.4 plots tasks at their `per_item` axis value. So the chart systematically understates effort,
  and **understates it most in the `quick_win` quadrant** — quick wins are only quick once setup is
  paid, and overhead *is* the setup. Demo: four dbt tasks at S(1.5) plot as four quick wins; the
  roll-up is `4 + 6 = 10` days, which is band **L**. The picture and the total contradict each other
  in the same document. [V by arithmetic on §4.3's own numbers.]
- **Comment preservation needs a dependency the plan doesn't mention.** §4.5: *"comments preserved
  where possible."* `assay/pyproject.toml:6-9` depends on `pyyaml>=6.0` only, and PyYAML discards
  comments unconditionally. This requires `ruamel.yaml` — a new runtime dependency on the tool that
  produces client deliverables, unlisted in §8. [V]
- **`impact / effort_axis` tie-breaking within a band.** With 4 impact values and ≤4 effort values,
  the ratio has heavy ties too, and it inverts oddly: a LOW at S is `4/1.5 = 2.67` while a CRITICAL
  at XL is `40/28 = 1.43`. "Set a real owner on a DAG" outranks a program-sized critical remediation
  within the band. The floor rescues criticals; nothing rescues HIGHs. [V]

---

## 11. Where the plan is telling itself a comfortable story

- **"D-3 lowers the stakes" is doing too much work.** D-3 is a *convention* ("internal-only"), not a
  mechanism. Meanwhile §4.5 specifies a polished markdown quadrant table and a per-offering roll-up,
  and §4.5 says it is *"the same renderer Assay's roadmap section will call in v2."* We are building
  a well-formatted, copy-pasteable client artifact and relying on people not to paste it. Compare
  `[A4]` in `ASSAY_PLAN.md:380-382`, where read-only *"graduates from principle to mechanism."* The
  plan demands mechanism of everyone else and grants itself principle. If v1 is internal, make the
  render say so in a way a consultant has to actively delete.
- **"Roadmap totals read as a quote — Medium (deferred by D-3)"** sits in §10 while §4.3 justifies
  the whole overhead model with *"the roadmap total is the number a proposal would quote."* The plan
  states its purpose is to produce the quote and then rates quote-risk as deferred. D-2 exists to
  prevent false precision; a printed "6-15 days × 4 items + overhead" roll-up reintroduces it one
  level up, where it looks more authoritative, not less.
- **"Scope creep past `[A4]` read-only — Severity: None."** `[A4]`'s stated rationale is *"the moment
  Assay fixes things it competes with the engagements it's meant to sell, and its risk tier jumps"*
  (`ASSAY_PLAN.md:380-382`). §8's last-but-one row and D-1's Phase 4 have an agent **creating Jira
  tickets** — a write into a client system, initiated by Assay, at agent judgment. Rating that "None"
  today, in the same table that sequences it, is exactly the underpricing `[A4]` exists to catch. It
  is out of v1 scope, but it should not be listed as a non-risk. [V for the `[A4]` text and the §8
  row; the risk judgment is [I].]
- **The strategic one.** `USE_CASES.md` opens with *"Every finding is a parsed fact, not an opinion."*
  That single sentence is the product. Putting a T-shirt guess in the same table as parsed facts
  transfers the guess's softness onto everything beside it. The `EstimateSource` enum protects *us* —
  a client sees a table. Expect the meeting to be about the one disputable number, and the thirteen
  indisputable ones to go undiscussed. `EstimateSource` is a good idea and I'd keep it regardless; I
  do not think it solves this, and §10 rating this "Medium, deferred" is the plan's most comfortable
  sentence. [I]

---

## Credit where it's due — verified true

- **§7's latent bug is real.** `report.py:115` ranks the roadmap by
  `-sum(deduction_for(severity))` with no `weight_for`; `rubric.py:76-90` does weight. Invisible only
  because every baseline weight is `1.0` (`qbiz_baseline.yaml:35-53`), and reweighting is advertised
  as *the* Tier-0 tuning move. **Fix and ship this independently of the matrix** — it is a real
  correctness bug with a one-line trigger and it should not wait on a design argument.
- **§6's corrections check out.** `harness/src/qbiz_harness/hitl.py` and `model_policy.py` both
  exist; `mcp/mcp_jira/` exists with `mcp.yaml`, `src/`, `SETUP.md`.
- **Adapter-not-inheritance for `Finding → Task`**, and the core-imports-nothing-Assay-specific
  discipline for D-4, are right and cheap.
- **Reusing the `Narrator` Protocol + deterministic-fallback shape** for `Estimator` is the correct
  instinct and matches `assessor.py:25-48`.
- **§5's identification of dependency clustering as the agent's real value** is the sharpest
  observation in the document. I'd build on that instead of the effort numbers — see Alternative C.
