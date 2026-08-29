# Engineer review — `PRIORITY_MATRIX_PLAN.v1.md`

*Reviewer: Engineer. 2026-08-07. Everything marked **[V]** I checked in the code; **[I]** is inference.*

---

## Bottom line

The feature is worth building and about a third of this plan is the right build. The other two
thirds are paying for a second axis that, **in v1, does not exist**: effort is derived entirely from
`defaults_by_offering`, so every finding sharing an offering gets an identical effort value, and the
median-split quadrant math in §4.4 is an expensive way to re-render the offering grouping
`report.py` already produces. Two of the plan's load-bearing "this is cheap, the machinery exists"
claims are wrong — §4.3's `apply_overrides` reuse (there is no generic machinery; every section is
hand-written) and §5's HITL availability (`hitl_checkpoint` is `async`, Assay is 100% synchronous).
Meanwhile the two genuinely hard problems — a stable `Task.id` over findings that have no id, and
`MEASURED` provenance over findings that carry no counts — get one line each. §7's latent bug is
**real**, but the prescribed fix is described in terms of code that does not exist. My estimate for
the plan as written is 1400–1800 lines including tests, roughly 2–3× what the §8 "Before Phase 3"
slot implies. A cut version delivers ~90% of the value in ~350 lines. Details below,
most-important-first.

---

## 1. [V] The effort axis is a constant per offering, so v1 has no second axis

In v1 nothing sets effort except `defaults_by_offering[finding.offering].per_item` (§4.3). Findings
carry `offering` (`findings.py:76`) and the baseline catalog has five entries
(`config/qbiz_baseline.yaml`), of which the plan's own defaults assign only two distinct per-item
bands (`S` for `dbt_startup_kit`/`ai_advisory`, `M` for the other three). So on a real run:

- effort is a pure function of `offering` — a lookup, not a measurement;
- a typical pulse assessment produces 6–15 findings across 2–3 offerings, i.e. **one or two distinct
  effort values across the whole task set**;
- median-splitting a two-valued axis puts everything on one side or splits on the offering boundary.
  The "quadrant" is then a renaming of "which offering is this in," which `report.py:104-121` already
  groups by.

The 2D shape only starts carrying information once a consultant hand-types efforts — which is the
`sync` path, i.e. the second run. **The plan's primary deliverable does not work on its first run and
the plan does not say so.**

That is not an argument against the feature, it is an argument against §4.4's machinery. Ship the
matrix as a *table with an effort column* and a computed `impact / effort_axis` ranking (§4.4 rule 3
alone), which is monotone, degenerate-free, needs no median, no fallback thresholds, and no
`min_task_count` config. Add quadrants in v2 when there is real hand-typed effort in the file to
split on. Cost saved: the median/fallback logic plus its whole test matrix, ~150 lines and the
fiddliest tests in the plan.

What you lose: the word "matrix" in v1. You keep the P-labels (derive them from the ratio ranking +
the severity floor, which is what actually determines them in practice — see #3).

## 2. [V] §4.3's "parsed and merged by the existing `apply_overrides` machinery" is not true

There is no generic machinery. `apply_overrides` (`config.py:196-258`) is 60 lines of bespoke,
per-section code: an explicit block for `severity_weights`, one for `bands`, a hand-rolled
merge-by-id loop for `dimensions` (`config.py:220-236`), another for `offerings`
(`config.py:238-249`), and a hand-built return. `parse_config` (`config.py:156-174`) is the same
shape. Nothing in either dispatches on section name or reflects over fields.

Adding `effort:` therefore costs, concretely:

- `EffortBand` + `EffortDefaults` frozen dataclasses, and a fourth field on `AssessmentConfig`
  (`config.py:83`, `frozen=True, slots=True`) — plus a default so no existing construction site
  breaks;
- `_parse_effort_bands` / `_parse_effort_defaults` with the same raise-on-malformed discipline as
  `_parse_bands` (`config.py:128-137`) — band id uniqueness, `days` a 2-list, `axis` numeric and
  inside `days`, `per_item`/`overhead` referencing declared band ids;
- a fifth hand-written merge block in `apply_overrides` with a *third* set of semantics: bands
  replace-wholesale (like `bands`) or merge-by-id (like `dimensions`)? The plan doesn't say. Pick
  merge-by-id or a profile can't retune one band without restating four.
- accessors (`band_for_id`, `default_for_offering`) mirroring `weight_for`/`deduction_for`.

Call it 110–130 lines of `config.py` plus ~15 tests in the style of `test_config.py`. Real, tractable,
and *not free*. The plan should say so; a reader budgets zero for this today.

Minor but in the same family: §4.1 types `effort: EffortBandId  # "S" | "M" | "L" | "XL", ids from
config`. Those two halves contradict each other, and the codebase has a hard rule about which one
wins (`findings.py:24-31`, `config.py:5-11`: registry entries, not enums). It has to be `str`.

## 3. [V] §7's bug is real; §7's fix is described in terms of code that doesn't exist

**The bug is real.** `report.py:113-116` ranks offering groups by
`-sum(rubric.deduction_for(f.severity) for f in kv[1])` — no dimension weight — while `overall_score`
(`rubric.py:76-90`) is a dimension-weighted mean. Every baseline weight is `1.0`
(`qbiz_baseline.yaml`), so it is invisible today, and `profile.py:20-23`'s own docstring example is
`data_quality: weight: 2.0`, i.e. the first thing a real profile does exposes it. Good catch.

**Two things §7 says about the code are wrong:**

1. *"one `impact_of()` used by the scorecard ordering"* — **there is no scorecard ordering.**
   `report.py:61` iterates `assessment.scores.items()`, which `score_dimensions` returns in rubric
   registry order (`rubric.py:49-53`). Rows are in config order and nothing sorts them. There is
   nothing to unify on that side.
2. `overall_score` **cannot consume `impact_of()`.** It is a weighted mean of per-dimension *scores*
   (`rubric.py:83-90`), not a sum of weighted deductions, and it has a deliberate zero-total-weight
   branch (`rubric.py:84-89`). Rewriting it to go through a per-finding `impact_of` changes the
   overall score, which is the number on the front page, for reasons unrelated to this feature.

So the honest framing is not "unify three call sites." It is: **`impact_of()` is new, and it has
exactly two callers — the roadmap ranking and the matrix.** That is a 3-line change to `report.py`
plus a ~6-line function, and it should be its own commit landed before any of this, so it can be
reviewed on its own merits. Which it needs, because it is arguably a design change and not purely a
fix: the roadmap groups by *offering*, and an offering group spans dimensions, so "weight the group's
risk by its findings' dimension weights" is a defensible choice rather than an obviously-correct one.
Land it, but land it as a decision with a test, not smuggled in as a bug fix inside a 1500-line
feature.

`impact_of`'s body as written in §4.2 is correct — `deduction_for` (`config.py:79`) and `weight_for`
(`config.py:70`) both exist with those signatures.

## 4. [V] `Task.id` "stable across regeneration" is the hard problem and the plan spends one clause on it

§4.5 makes `id` stable across regeneration a requirement and §10 correctly names sync-clobbering as
the highest risk. But:

- **`Finding` has no id.** `findings.py:62-79`: `dimension, severity, title, detail, remediation,
  offering, subject, evidence`. Nothing stable, nothing unique. (It is also unhashable —
  `@dataclass(slots=True)` with default `eq=True` sets `__hash__ = None` — so no set-based dedup.)
- **Titles embed live counts.** `dbt.py:147` `f"Test coverage is {test_cov}% ({len(untested)} of
  {total} models untested)"`; `dbt.py:162`, `dbt.py:178`, `dbt.py:199` the same. A title-derived id
  churns on *exactly the re-run the sync command exists for* — the client fixed three models, the
  title changes, the id changes, the task is marked "disappeared," a new one appears, and the
  consultant's typed effort and notes are stranded on the tombstone. That is the §10 failure mode,
  arrived at by the default implementation.
- **Severity also moves.** `dbt.py:146` `Severity.HIGH if test_cov < 50 else Severity.MEDIUM`. So
  severity is out as an id component too.

The only stable tuple available is `(collector_name, dimension, offering, subject)` — and `subject`
is `None` on most of the dbt findings above (`report.py:100` already defends with `f.subject or "—"`),
and `collector_name` is not on the `Finding` at all; it lives on `CollectorResult.name`
(`collectors/__init__.py:50`) and is dropped when the engine flattens (`engine.py:204`).

**This is the piece to design before writing anything else**, and my read is that it forces a small
change to the facts layer: a `key: str` field on `Finding` that each collector sets to a stable
slug (`dbt.test_coverage`, `dbt.doc_coverage`, …), independent of counts and severity. That is
correct, it is cheap in `findings.py`, and it is *not* cheap in blast radius — four collectors
(`dbt.py`, `airflow.py`, `ai_usage.py`, `cloud_posture.py`, plus `TEMPLATE.py`) and their ~50k
characters of tests. Budget 150–250 lines of churn for it and put it in §8 as its own row. Do not
let it be discovered during implementation of the merge.

## 5. [V] `EstimateSource.MEASURED` is not implementable in v1

§3 defines `MEASURED` as "arithmetic over a countable fact (4 untested models × rate)." Two blockers:

- **There is no per-finding count.** The counts exist only interpolated into title strings
  (`dbt.py:147`) and in `CollectorResult.stats` (`dbt.py:119-127`) under collector-specific ad-hoc
  keys (`test_coverage_pct`, `sources_without_freshness`) with no link back to the finding they
  belong to. `Assessment` keeps `collector_results` (`engine.py:65`) so the stats survive, but
  joining a stat key to a finding requires a hardcoded per-collector table.
- **There is no rate.** §4.3's schema has bands and per-offering defaults; nothing maps "one untested
  model" to a duration.

And a per-collector stat→finding table inside `prioritize.py` is precisely what `config.py:9-11`
calls a framework bug ("If adding an assessment domain requires editing `engine.py`, `rubric.py`, or
`report.py`…"), one module over.

Keep the enum member — it costs nothing and §3's retrofit argument is right — but **mark it reserved
and unused in v1**, and delete the parenthetical that implies it works. Otherwise the first
implementer spends a day discovering this.

## 6. [V] "comments preserved where possible" adds a third dependency

Assay depends on `qbiz-agent-harness` and `pyyaml>=6.0`, full stop (`assay/pyproject.toml`).
`yaml.safe_load` (`config.py:179`, `profile.py:116`) discards comments irrecoverably; round-tripping
them needs `ruamel.yaml`. Cut the requirement. A `notes:` field that survives the merge is the actual
need and it is a plain data field. If you want a header comment on the generated file, write it as a
literal string at emit time.

## 7. [V] §5's HITL "not blocked, available now" understates the cost by an order of magnitude

`hitl_checkpoint` is `async def` (`hitl.py:90`) over an `async` `ApprovalTransport.request_approval`
(`hitl.py:55`). Assay is synchronous end to end: `run_assessment` (`engine.py:127`), `run_profile`
(`profile.py:202`), `main`/`argparse` (`cli.py:98`). Wiring a gate in means either `asyncio.run()`
around a leaf call in a sync CLI, or an async path through the CLI. Additionally, **no
`ApprovalTransport` implementation exists in this repo** — the Slack side is an MCP *tool*
(`mcp/mcp_slack/src/slack_mcp/tools/hitl.py:21`), not a Python object satisfying the Protocol, so an
adapter has to be written and there is no MCP transport binding in Assay at all yet (`profile.py:34`
notes MCP wiring is Phase 3; `build_collector_specs` takes fakes in tests).

"`hitl.py` ships" is true and "the accept gate is not blocked on Phase 5" is true. "Available now" is
not. **Agree with A-9's leaning — local CLI diff for v1** — and I'd go further and strike the HITL row
from §8 rather than leave it as "v1 or Phase 3."

Same family: §5 rule 2 wants a `ModelPolicy` band. Zero references to `ModelPolicy`/`model_policy`
anywhere in `assay/` today, and `ModelPolicy.__init__` requires a `tier_map` of concrete model
strings (`model_policy.py:80-88`) — which is the open `[D3]` provider decision. It is the right call
*when there is an LLM estimator*; it is not a v1 line item, and §8 already correctly parks the LLM
estimator in Phase 3. Move the tier-band bullet there with it.

## 8. [V] §6's "corrections to the record" check out

`mcp/mcp_jira/src/jira_mcp/jira_mcp.py` exists with `create_jira_ticket` (line 71),
`search_jira_tickets`, `add_jira_comment`, `review_jira_ticket`, `list_projects`. `hitl.py` and
`model_policy.py` are both shipped and both exported from `qbiz_harness/__init__.py`. No objection —
noting it so the §6 claims are marked verified rather than assumed.

## 9. [I] §4.3's `offering_total = overhead + Σ(per_item)` is underspecified in the one place it matters

The reasoning is right — naive summing overcounts setup — but the arithmetic is left dangling. Bands
carry a `days: [lo, hi]` *range* and an `axis` midpoint that D-2 says is never printed. So what is
`S + M + M`? If you sum ranges you get `[7, 12]` days, which is a number a consultant will paste into
a proposal — the exact D-3 risk, reintroduced by the roll-up rather than by the per-task rows. If you
sum `axis` values you have printed the axis, contradicting §4.3. If you re-band the sum you have lost
the additivity that motivated the overhead model.

My recommendation: **sum the day ranges and print them, and accept that this is the number [A8]
gates.** It is the honest output and D-3 keeps it internal. But say so in the plan, because the
current text implies a total exists without saying what it looks like on the page.

## 10. [I] `sync` merge semantics — what will actually be annoying

Assuming #4 gives you a stable key, the merge is a 4-way classification and each arm has a real
decision behind it:

| case | decision needed |
| --- | --- |
| key in both | keep `consultant` effort + `notes`; refresh `impact`, `title`, `severity`, `rationale`. **Does a refreshed `impact` silently reorder a matrix the consultant already reasoned about?** |
| key only in new | append. Where — end of file, or sorted position? Sorted position rewrites the whole file and makes the diff useless. |
| key only in stored | tombstone. Needs a field (`status: resolved`?) not in §4.1's `Task`, plus a rule for when tombstones are ever removed, or the file grows monotonically across an engagement. |
| key in both, `measured` contradicts `consultant` | this is open item [A10]. |

That is four arms × (a handful of cases each) and the file is the consultant's typed work, so the
tests have to be genuinely exhaustive rather than representative. **This is the single largest test
surface in the plan** — I'd budget more test lines than implementation lines here, ~200/150, and it
should be written first, before `init` even, because every other piece is easy to retrofit and this
one is not.

Two concrete mitigations worth adding to §4.5 as requirements, both cheap: (a) `sync` writes to a
temp file and renames, so a crash mid-write cannot truncate the consultant's file; (b) `sync`
refuses to run if it would drop any `consultant`-sourced value, as an assertion in the code path
rather than a property of the tests.

`Task` also needs a `status` field for the tombstone arm — §4.1's dataclass doesn't have one.

## 11. [I] `init` and `sync` each re-run the whole assessment; the CLI shape hides this

`qba assay prioritize init <profile.yaml>` (§4.6) takes a profile, so it calls `run_profile`
(`profile.py:202`) → collectors re-run, engine re-runs, and if a narrator were configured the
*narration* re-runs and re-spends. `sync` does it again. Today collectors are pure artifact parsing
so this is free and fine, but it means `prioritize` is not a cheap local operation and it will stop
being free the moment Phase 3's connected collectors land. Either say `init`/`sync` accept a
serialized assessment as well as a profile, or state explicitly that narration is skipped on this
path. (`run_assessment` has no "collect and score only" mode today — `engine.py:212-265` always runs
stage 3, defaulting to `RuleBasedNarrator`, which is free but does mean a `prioritize` run produces
narrative text nobody reads.)

The argparse plumbing itself is genuinely cheap — `cli.py:71-95` already nests subparsers with
`set_defaults(handler=...)`, and a third level is ~25 lines. That part of §4.6 is correctly priced.

## 12. [I] Where the estimate is wrong, summarised

| Piece | Plan implies | My estimate (impl + test) | Note |
| --- | --- | --- | --- |
| `impact_of()` + roadmap fix (§7) | "unification," bundled | **20 + 30** | Cheaper than described. Land first, standalone. |
| `effort:` config (§4.3) | free ("existing machinery") | **120 + 120** | See #2. Nothing is free here. |
| Stable finding key (#4) | not listed | **80 + 180** | Not in the plan at all. Touches 4 collectors + tests. |
| `Task`, `EstimateSource`, adapter (§4.1) | — | **90 + 90** | Correctly cheap. |
| Quadrant/median + fallback (§4.4) | — | **150 + 200** | Cut it (#1). Highest cost-to-value ratio in the plan. |
| YAML emit + `sync` merge (§4.5) | one bullet | **200 + 250** | The real work. See #10. |
| Markdown render (§4.5) | — | **80 + 60** | Fine. |
| CLI (§4.6) | — | **60 + 60** | Correctly cheap. |
| **Total as written** | "before Phase 3" | **~1400–1800** | |
| **Total, cut version** | | **~600–700** | |

For calibration, `test_report.py` is ~380 lines and `test_config.py` ~180, so "200 test lines" here
means a file the size of the ones already in `assay/tests/`.

## 13. What I'd cut, concretely

Ship v1 as:

1. `impact_of()` + the `report.py:115` fix, as a separate commit.
2. A stable `key` on `Finding` (#4) — the prerequisite nobody has budgeted.
3. `effort:` config: bands + `defaults_by_offering` + `fallback`. Keep `overhead`/`per_item`; it is
   in the schema at no extra parse cost and #9's decision can wait.
4. `Task` + `EstimateSource` + the `Finding → Task` adapter, exactly as §4.1 has it.
5. Ranking by `impact / effort_axis`, with the `priority_floor: {critical: P0}` override. **No median,
   no quadrants, no threshold fallback.**
6. YAML emit + `sync` merge, with the four arms of #10 nailed down and tested first.
7. Markdown render: one ranked table with a `P`, an effort band label, a day range, and the
   per-offering roll-up.
8. `DefaultEstimator` as the only estimator.

Defer: quadrants (until a file exists with hand-typed effort to split), `MEASURED`, the HITL gate,
the model-tier band, the LLM estimator, dependency clustering.

What you lose by deferring quadrants: the visual that §4.4 calls "the deliverable." I'd argue you
lose less than it sounds, because per #1 v1's quadrant plot is a scatter with two x-values — it would
look broken in front of a consultant and they'd conclude the tool doesn't work. Better to ship the
ranked table that is honestly what v1's data supports, and add the plot in v2 when `sync` has been
run once and the effort column has real variance in it.

## 14. One thing I'd push back on beyond scope, and am not doing

§5's "what the agent is actually better at — clustering findings into workstreams and identifying
sequencing dependencies" is, I think, the strongest idea in the document, and it is parked in Phase 3
behind the `[D3]` provider decision. It is also the only part that couldn't be done with a lookup
table. If it turns out that effort estimation is the weak half and dependency inference is the real
product, the phasing here is upside-down. **Not proposing a change — flagging it for the Architect,
since it's a sequencing judgment, not a cost one.**
