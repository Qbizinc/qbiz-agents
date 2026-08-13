# Harness Plan — Architect Review

Reconciles [`harness_plan_engineer.md`](harness_plan_engineer.md) and
[`harness_plan_challenger.md`](harness_plan_challenger.md), both written independently against the
same scope (Required Decisions, per-component open items, Fleet Operation, Data Sensitivity J1–J9)
with Decisions Locked and shipped work held fixed. I read both in full, then checked the two
code-level claims that mattered most against the actual source (`orchestration.py`,
`cost_governor.py`) before ruling — an implementation claim in a review is a claim about the code,
not about the prose, and it's cheap to verify.

Rulings below are ordered the way I order everything: **by what it costs to leave wrong**, not by
which section of the plan it falls under. A one-word documentation fix that prevents an oversold
claim reaching a client outranks a sequencing preference, regardless of which persona raised it.

---

## 1. The Ring 1 "Total" claim — fix now, this is client-facing

**Challenger's finding, uncontested, and I agree with it fully.** The Enforcement Perimeter table
calls Ring 1 "**Total** — in-process, un-bypassable." That's true against the model's reasoning. It
is not true against an engineer who forgets to call `governor.record_action` before a send — and
the plan's own README says the harness is "à la carte... you construct each control... at the right
point," which is an admission that wiring is manual and therefore fallible. An overclaim in an
internal planning doc is cheap to carry. The same sentence in a client conversation is a promise,
and "we said un-bypassable and it wasn't wired" is the kind of gap that costs trust to walk back —
expensive to undo, near-free to fix now. That asymmetry is why this ranks first.

**Ruling:** change "Total" to "**Total, once wired**" in the table, and add Challenger's Gate 1
item — a static check that every consequential action in an agent's code path is preceded by a
matching governor/access-control call. Start it grep-shaped; it doesn't need to be clever, it needs
to exist before the first client conversation that uses the word "un-bypassable."

## 2. `with_retry` silently retries `HarnessError` — this is a bug, not a proposal

**Challenger's finding. I verified it against `orchestration.py` directly — confirmed as written.**
Line 47 reads `except (asyncio.TimeoutError, Exception)`, which is exactly `except Exception`
(`TimeoutError` is already an `Exception` subclass). Any `HarnessError` raised inside a step
wrapped in `@with_retry` — a `BudgetExceededError` from `governor.pre_call`, a `ModelPolicyError`
from `policy.check` — gets caught and retried with backoff up to `max_attempts` times before it
finally propagates. Every other component's contract, and this module's own docstring, promises the
opposite: a harness rejection surfaces immediately.

I'd normally treat shipped Phase 1 code as settled, the same as Decisions Locked. A bug isn't a
decision, though — it's the implementation not matching its own stated design, which is exactly what
this kind of review exists to catch, decisions-locked or not.

**Ruling:** fix immediately, ahead of any of the proposal work below. Two-line change — catch
`asyncio.TimeoutError` alone for the transient case the decorator is meant to cover, let
`HarnessError` propagate on first raise — plus a regression test asserting a `HarnessError` raised
inside a retried step is not retried. This is not scope creep on the review; it's a defect found
during it, and defects that silently defeat a safety control don't sit in a backlog.

## 3. Kill switch naming — accept as scoped, don't build more

**Challenger's finding, and Challenger already scoped the fix correctly — I'm ratifying, not
expanding it.** `CostGovernor.kill()` is documented as "a hard global stop," but I confirmed against
the code: `CostGovernor` is a plain per-run instance with no shared state: `kill()` sets one
instance's `_killed` flag. At fleet scale, many concurrent `CostGovernor`s exist per cohort; calling
`.kill()` on one stops that run, not the cohort. "Kill switch" + "hard global stop" in the same
sentence reads, correctly, as more than that.

Challenger's own proposed fix is the cheap one — rename or re-scope the claim — not "build a real
cross-process kill mechanism," which would be new infrastructure against no concrete forcing case,
exactly the pattern Engineer's review (§4 below) argues against elsewhere. I'm holding Challenger to
the same discipline here, and it already meets it.

**Ruling:** rename to `halt_run()`, or keep the name and correct the docstring/README to say "stops
this run, not the fleet" — either is fine, but the current wording must not survive to a fleet-scale
demo unchanged.

## 4. Data Sensitivity ledger — sequencing and structural holes are not the same argument

**This is the one place the two reviews needed active reconciliation, not just merging.** Engineer
argues, correctly, for building the ledger narrow first — human-attested-only, single-scope,
no-expiry, no-bulk-attestation — against one real engagement, deferring expiry/bulk/multi-scope
until a second real case forces the shape, the same "design from evidence, not imagination"
discipline the harness already applies to the evaluator. I agree with that sequencing on the merits;
it's the same argument I'm making in §7 below about D4 and D7, and I'd be inconsistent to accept it
there and not here.

Challenger separately finds that the admission gate, as specified, has structural gaps: declared-
classification lookup isn't independent verification (it re-reads the same producer tag J1 already
trusts, so a mislabeled column sails through "machine-cleared"); self-attestation has no segregation
of duties (attester can equal requester under today's open-write-access default); and
"derived content inherits" names a rule with no named enforcement mechanism.

The risk in just adopting Engineer's sequencing wholesale is that "build the minimal version first"
quietly absorbs Challenger's findings into the deferred pile along with expiry and bulk scoping —
and they don't belong there. Expiry, bulk/glob attestation, and multi-scope resolution are
**additional dimensions** the ledger doesn't have yet. Segregation of duties, a consistency check on
the declared-classification path, and a named derivation-stamping obligation are **integrity
properties of the two admission paths that exist in any version**, including the minimal one. Ship
the minimal ledger without them and it isn't a smaller safe thing — it's the same-sized hole in a
smaller box.

**Ruling:** Engineer's sequencing stands — build narrow, against one real engagement, don't
speculatively design expiry/bulk/multi-scope. But the minimal build ships with all three of
Challenger's fixes included, not deferred: (a) `attested_by` distinct from the requesting
`agent_id`/operator, enforced in the attestation config block itself; (b) a sample-based consistency
checker — deterministic pattern detection run against a sample of objects tagged below `restricted`
at manifest-ingestion time, flagging disagreements for human review; (c) an explicit statement, and
enforcement point, that content reaching the model without passing through the shared extraction
utility or the gate is unattested by default — "no," not "usually." None of these are new
dimensions; they're the difference between the minimal version being genuinely safe and merely
smaller.

## 5. D1 — the two reviews converge, and the combination is better than either alone

Engineer says: decide D1 now, as env-var-from-launcher, because Fleet Operation already says that's
where the manifest points and there's no cost to deciding what's already been argued for. Challenger
says: the table asks the wrong question — the real issue for a fleet deployment is that `agent_id`
should be *derived* from a `job → cohort → agent_id` manifest lookup, not just *carried* in whatever
transport; env-var-vs-token is a question about the transport once the value is already trusted.

These aren't in tension. Challenger specifies what Engineer's "decide now" should actually decide.

**Ruling:** for fleet deployments, `agent_id` is derived at launch from the manifest lookup keyed on
the job identity the orchestrator (Airflow) already knows, and carried across the process boundary
as an env var — Engineer's cost argument for the transport, Challenger's correction of what's being
transported. For a bare single-agent deployment with no manifest, plain env-var-from-launcher stands
as originally framed; Challenger is explicit that D1-as-written is fine there, and I agree. This is a
fully reversible wiring decision, not an irreversible architecture bet — decide it now, as both
reviews independently conclude, and it unblocks Phase 3.

## 6. Fleet manifest — merge semantics and diff governance, both accepted, both narrow

Engineer flags that three-layer config inheritance has no specified merge semantics and proposes the
narrowest resolvable version: replace-at-top-level-key, no deep merge, hand-verifiable at ~12
cohorts. Challenger flags that the manifest is the blast-radius control surface and a tier-*decrease*
diff looks identical, in review, to a routine reassignment, proposing a narrow pre-merge check that
flags only decreasing diffs for an explicit reason and a second reviewer.

Neither conflicts with the other — one is about resolving the config correctly, the other about
governing changes to it — and both are scoped the way I want everything in this plan scoped: small,
targeted at the actual failure mode, not general machinery built ahead of need.

**Ruling:** accept both as specified. Replace-at-top-level-key ships with the resolver; the
tier-decrease check ships as a pre-merge script, not a policy engine, and explicitly does not reopen
Decision 4 (open write access) — it flags one specific direction of change, not authorship.

## 7. D4, D7 — premature abstraction, accept Engineer's deferral, uncontested

Engineer's argument holds and Challenger doesn't contest it: both D4 (audit backend) and D7
(classification source) are specifying multi-engine/multi-provider interfaces against a single real
implementation (JSONL; none). That's the shape the harness's own shipped components deliberately
avoid — pure, narrow, built against a real call site, not a hypothetical one. Consistent with my
ruling in §4, I'm applying the same standard here.

**Ruling:** defer the SQLAlchemy fallback and the MIP/Purview-style provider generalization to
Deferred Concerns; extract the interface from the second real implementation when one exists, not
from the current zero. This doesn't block anything — D4 isn't needed before a HIGH+ deploy, and D1/
D3 gate client work regardless.

## 8. Smaller accepted items, uncontested by the other persona

- **J9 → Phase 1.** Engineer's argument is sound: static, agent-agnostic, zero prerequisites, same
  shape as what already shipped there. Scheduling change, not a design change. Accepted.
- **J3 as a near-free increment.** `output_validator.check_scope()` already implements the pattern
  J3 needs; once J6 exists, this is close to reuse, not new design. Add it to the "sensible first
  deliverables" list alongside J2/J7/J8/J9. Accepted.
- **Component 6's stale "still to specify" bullet.** I checked this myself: `orchestration.py`
  already takes `timeout` as a call-site parameter, exactly as Engineer describes. The plan
  contradicts its own Phase 1 tracker. Drop the bullet. Accepted, verified.
- **Component 8's vague "unattended/overnight" bullet.** Replace with the concrete, code-grounded
  gap: `TimeoutPolicy.ESCALATE` raises `HitlEscalationRequired` with no paging mechanism behind it —
  a policy name with fail-closed's behavior and a different exception type. Accepted; this is a
  more honest statement of the same open item, not new scope.
- **Cohort blast-radius sentence.** Challenger's point that a cohort bounds a *ceiling*, not
  per-job minimal access, is correct and currently only implicit. One sentence in Fleet Operation.
  Accepted.

## 9. No change

D2, D5, D6's mechanism, D8, and D9 were reviewed independently by both personas and both concluded
the same thing: correctly sized, safe defaults exist, not on the critical path. Two independent
reviews converging on "leave it alone" is the strongest signal this plan gets anywhere in this
exercise — no ruling needed because there's no disagreement to rule on.

---

## What I'm not doing

I'm not editing `HARNESS_PLAN.md` itself. This document is a ruling on two proposals, not an
implementation — §2's bug fix and §1's wording change are both small enough to land immediately once
someone signs off, but that's a call for whoever owns the file, not something I do unilaterally off
a review exercise. If the ruling above is accepted, the concrete next step is two PRs: one for the
`with_retry` fix (§2, has a regression test attached), one for the Enforcement Perimeter wording +
Gate 1 coverage check (§1) — both small, both high-consequence-to-leave-wrong, both independent of
everything else in this document.
