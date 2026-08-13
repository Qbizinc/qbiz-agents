# Harness Plan — Challenger Review

Scope, per the working agreement: Decisions Locked and everything already shipped (Phase 0, Phase
1, the completed slices of Phase 2/7) are fixed context, not up for relitigation. This review is
aimed entirely at what's still open — the Required Decisions table, the "still to specify" items,
Fleet Operation's manifest design, the Data Sensitivity / Content Admission section, and the
Enforcement Perimeter's honesty about its own coverage. I read the plan in full and the actual
`src/qbiz_harness/` implementation, not just the prose, so some of what follows is "the code
doesn't do what the plan implies," not just "the plan should say more."

One thread runs under most of what follows, so I'll name it once up front instead of repeating it:
**every control in this document is enforced only where the code is actually wired to call it.**
The plan is candid that the harness is "à la carte... you construct each control in Python and
call it at the right point" (README, Status). That's a reasonable engineering choice. But it means
the Enforcement Perimeter table's claim that Ring 1 is **"Total — in-process, un-bypassable"** is
true only against the *model's* reasoning — it is not true against a human who writes the agent
code and simply doesn't call `governor.record_action` before a send, or wraps a guarded step in a
decorator that swallows the rejection (see the `with_retry` finding below). Nothing in Gate 1 as
specified verifies *coverage* — that every consequential action in a given agent actually routes
through a guard — only that the guards which *are* invoked behave correctly at their thresholds.
That's a real gap between "un-bypassable" and "un-bypassable if wired," and it's exactly the kind
of overselling Step 3 asked me to look for. I'd change one word in that table cell — "Total" to
"Total, once wired" — and add a Gate 1 item: a static check (grep-shaped is fine to start) that
every tool call / send / write in an agent's code path is preceded by a matching governor or
access-control call. Cheap to build, and it's the difference between a claim about the code and a
claim about *this specific agent's* code.

## D1 — the framing is answering the wrong axis

D1 is posed as "env var vs. signed token" — a question about how identity is *carried* from
launcher to harness. But Fleet Operation already answers a more important question the table
doesn't ask: how identity is *derived*. Once `fleet.yaml` exists, the correct source of truth for
`agent_id` is "which job/DAG-task actually invoked the launcher, looked up in the manifest" — not
"whatever string got set in the environment when the process started." Env-var-vs-token is a
question about the transport once you already trust the value; it says nothing about whether the
value was *computed* from the job that's actually running or just typed in by whoever wrote the
launch config for a test run. For a fleet deployment, I'd resolve D1 as: the launcher derives
`agent_id` from `job_id → cohort → agent_id` in the manifest, keyed on the job identity the
orchestrator (Airflow) already knows independent of anything the harness or agent supplies — the
carrier (env var or signed token) is then just how that derived value crosses a process boundary,
and stops being the interesting decision. For a bare single-agent deployment with no manifest, the
env-var-vs-token question is still real and D1 as written is fine there — I'm not saying drop the
decision, I'm saying it has two different right answers depending on whether a manifest exists, and
the table currently implies one axis for both.

## Fleet manifest — the blast-radius control is also the easiest thing to quietly widen

The manifest (`job → cohort → agent_id`) is explicitly *the* management surface — "the whole
topology reviewable and diffable in one place." I'd take that claim further than the plan does:
reviewable and diffable is a property of git, not a property this document adds any enforcement to.
Moving a job from `finance-tier-HIGH` to `platform-tier-MEDIUM` is a one-line YAML edit that looks
identical, in diff form, to a routine reassignment — and it silently drops that job's access
allowlist, model-tier ceiling, and HITL requirement to whatever the lower cohort's template grants.
Nothing in the plan distinguishes "this diff changed what a job is allowed to do" from any other
manifest diff. I'd add one narrow, cheap control: a check (can be a pre-merge script, doesn't need
to be a person) that fails when a manifest diff *decreases* a job's cohort risk tier or shrinks its
declared data-sensitivity floor (J5) without an explicit `reason:` field and a second reviewer on
that specific line. This is not a proposal to reopen Decision 4 (repo-wide CODEOWNERS) — it's
narrower and compatible with open write access: everyone can still edit the file, but a
tier-*decrease* is flagged distinctly from a tier-*increase* or a same-tier move, because only the
decrease is the direction an honest mistake or a shortcut-under-deadline-pressure would take.

Separately: cohort grouping by `(risk tier × system/credential scope × owner)` collapses 100 jobs
to ~5–15 identities, and the plan frames this as solving both the cost problem and the blast-radius
problem. It solves cost. It only partly solves blast radius — every job inside a cohort still
inherits the *full* permission set of that cohort, not just what it individually needs. A job that
only ever touches one Airflow DAG's Slack channel still runs under `finance-tier-HIGH`'s complete
allowlist if that's its cohort. That's an acceptable trade (12 templates beats 100 bespoke configs,
and the plan says as much implicitly), but it should be said explicitly rather than left for a
client to assume "same cohort" means "same access," because it doesn't — it means "same *ceiling*
on access." One sentence in the Fleet Operation section would close this.

## Data Sensitivity & Content Admission (J1–J9) — this is where the exposure actually is

This is the section that decides what leaves the boundary, so it gets the most scrutiny, per the
"weight by exposure" instruction.

**Two of the three admission paths are "trust the same declaration twice," not independent
verification, and the document doesn't say so.** Content admission has exactly two paths in:
*attested clean* (a human says so) and *machine-cleared* (passes the configured checkers — "secret
patterns, **declared-classification lookup**, structural rules"). Look closely at
"declared-classification lookup": that checker doesn't inspect content, it re-reads the same tag
J1/J6 already trusts from the producer. If a dbt model is mislabeled `internal` when a column is
actually PII — a labeling mistake, not a malicious one, and the single most likely failure mode for
a taxonomy authored by whoever wrote the dbt model — "machine-cleared via declared-classification
lookup" will wave it through, because the check *is* the declaration. This isn't a hole in J2's
redaction (which the plan is already honest about — "weak, do not sell this" — good, that
admission is exactly right and I'm not touching it). It's a hole in the *admission gate itself*
believing it has two independent legs when it structurally has one and a half: secret-pattern
matching is genuinely independent; declared-classification lookup is not. I'd add a cheap,
low-precision **consistency checker** — not a redactor, a QA signal — that runs deterministic
pattern detection against a *sample* of objects tagged below `restricted` and flags disagreements
for human review at manifest-ingestion time, not per-request. It doesn't need to be good; it needs
to exist, because right now nothing checks the checker.

**Self-attestation has no segregation of duties, and this collides with something Decision Locked
#4 already flagged.** The "attested clean" path is a human clearing content, "recorded with
identity" — but nothing says the attester can't be the same person who wants the content sent, and
under open access (Decision 4) that's everyone. I want to be precise about what I'm arguing, because
Decision 4 is declined territory and I'm not reopening it: Decision 4's own stated rationale for
*not* restricting write access yet is that it "only matters once this code lands on client hardware
or an audit requirement narrows who may change the enforcement boundary." Attestation *is* changing
the enforcement boundary — at the grain of one artifact, one clearance at a time, on a live client
engagement, which is precisely the trigger condition Decision 4 names as the thing that would flip
the calculus. I'm not proposing CODEOWNERS on the repo. I'm proposing something narrower and
orthogonal to that decision: attestation authorization scoped to the admission gate specifically —
attester ≠ requester on `restricted`/regulated content, enforced by the `attestation` config block
itself (a second `attested_by` distinct from the run's `agent_id`/operator), not by repo permissions
at all. This can ship without touching who may edit code.

**"Derived content inherits" is a stated rule with no named enforcement mechanism.** The plan
already correctly identifies this as "the most likely way this mode gets quietly defeated in
practice" — that's the right call, and I have nothing to add to the *diagnosis*. What's missing is
the *how*: which piece of code stamps a derived artifact with its parent's content hash and
un-cleared status? If the answer is "whatever extraction tool the engagement uses, by convention,"
then an ad hoc script a consultant writes to "just pull the structure" produces content with no
lineage tag at all — and depending on whether that content ever gets routed through the admission
gate in the first place (see the wiring point at the top), it may not default-refuse, it may just
never be checked. I'd make this concrete: name the derivation-stamping obligation as a property of
whatever shared extraction utility ships with `admission.py`, and treat any content that reaches the
model *without* having gone through that utility or the gate as itself the thing J7's
`default_confidential` posture exists to catch — which means the honest answer to "is my ad hoc
script safe" has to be "no, by design," not "usually."

**What's already right here and I'd leave alone:** the classifier-cannot-be-the-leak callout, the
coverage-vs-correctness distinction in the `default_confidential` promise, and leading with the
endpoint (J9) over redaction. All three are the harness holding an honest line under what's
probably commercial pressure to claim more, and that's the right call — I looked for something to
push on in each and didn't find one worth manufacturing.

## Kill switch — the name promises more than a per-run object delivers

`CostGovernor.kill()` is documented, correctly, at the module level as "a hard global stop." But
`CostGovernor` is a per-run instance — the launcher constructs a fresh one per invocation (this is
explicit in the model-tier section: "like `CostGovernor`, the launcher constructs it with the right
policy for the run"). At fleet scale, a cohort's reasoning tier can have many concurrent incident
invocations running simultaneously, each with its own `CostGovernor`. Calling `.kill()` on one
stops *that run*. It does not stop the cohort. An operator reading "kill switch" and "hard global
stop" in the same sentence, in a client-facing conversation about a runaway fleet, will reasonably
expect the second meaning. This is a naming/scope gap worth fixing before it's demoed as more than
it is — either rename the in-process one (`halt_run()`) and reserve "kill switch" for a real
cross-process mechanism the Fleet Operation section would need to design (a shared flag in the audit
backing store, checked at the top of each guarded call), or explicitly scope the current one in the
docstring and README as "stops this run, not the fleet" so nobody demos it as the latter.

## One implementation bug worth a two-line fix

`orchestration.py`'s `with_retry` catches `except (asyncio.TimeoutError, Exception)` — which is just
`except Exception`, since `TimeoutError` is already an `Exception`. That means any `HarnessError`
raised *inside* a retried step — a `BudgetExceededError` from `governor.pre_call`, a
`ModelPolicyError` from `policy.check` — gets silently retried with backoff up to `max_attempts`
times before it finally propagates, instead of surfacing immediately the way every other component's
docstring promises ("raises... before the action runs"). A consultant who wraps a whole guarded step
in `@with_retry` (a natural thing to do, since it's the documented pattern for bounding a step) gets
a harness rejection retried 2–3 times before it's honored. Low exposure on its own — this is the
orchestration component, thin blast radius — but it's a real contradiction between what the module
promises and what it does, and a two-line fix (`except (asyncio.TimeoutError,) ` for the transient
cases the decorator is meant to catch, let `HarnessError` propagate immediately) closes it.

## Also fine as framed, no challenge

D2 (per-agent memory default), D5 (regex-first injection screening), D6's mechanism (fail-closed
default, already correctly the safe one), D8 (everything-MID-until-benchmarked default), and D9
(module over standalone tool) are all reasonably framed with real safe defaults and no bypass I
could find worth raising. I looked for a third option on each and didn't find one that beats what's
there.
