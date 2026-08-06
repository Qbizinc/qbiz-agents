# Harness Plan — Engineer Review

**Reviewer:** Engineer persona. **Scope:** the open ground only — Required Decisions (D1–D9),
the per-component "still to specify" items, Fleet Operation's manifest/inheritance proposal, and
Data Sensitivity (J1–J9). Decisions Locked, and everything marked done through Phase 1/2/7, stand
— I checked the shipped code against the plan's claims and it holds up (see the closing section).
I'm not re-opening any of that.

Bottom line up front: the code that exists is well-judged — small, pure, dependency-free
components that raise and let the call site do I/O. That discipline is worth naming because it's
the thing to protect going forward, and two of my recommendations below are exactly "keep doing
what Phase 1 did" applied to sections that haven't shipped yet. My pushback concentrates where the
plan starts speccing in full before there's a consumer to spec against — mostly Data Sensitivity
and the fleet manifest — and where a decision's stated cost doesn't match what the same document
says three sections later.

---

## 1. Required Decisions — where I'd push

**D1 (agent identity) is real but the plan is over-deliberating a decision it already answered.**
The decision table frames D1 as "env var vs. signed token," open. But the Fleet Operation section,
in the same document, says the fleet manifest "favors the env-var-set-by-launcher option over a
per-agent signed token." Those aren't equally expensive options — env-var-from-launcher is a few
lines; signed tokens mean issuance, rotation, and verification code, i.e. a second subsystem. Don't
let D1 sit "pending review" waiting on a signed-token design nobody has asked for yet. Decide it
now as env-var-from-launcher, since that's the direction the fleet manifest already commits to, and
revisit only if a concrete threat model shows up that env vars don't cover (e.g. agents invoked
across a network boundary where the launcher can't guarantee the process environment). This
unblocks Phase 3 sooner and costs nothing — it's picking the option the plan has already argued
for.

**D4 (audit backend) is speccing a three-engine abstraction before there's a second engine.**
"Pluggable, warehouse-agnostic writer" sounds right in the abstract, but concretely: JSONL exists
and works, and nothing else does. Designing the interface now, against zero real Snowflake/BigQuery
integrations, means guessing the abstraction from imagined requirements. That's the failure mode
the harness's own components avoid everywhere else (pure functions, no I/O baked in early). I'd
defer interface design until the first client engagement that actually needs a warehouse writer,
then extract the interface from that one real implementation plus JSONL — a rule-of-three call, not
a build-it-now call. This doesn't block anything: D4 is explicitly not needed before a HIGH+
production deploy, and D1/D3 gate client work regardless, so there's no schedule pressure forcing
an early abstraction here.

**D7 (classification source) has the same premature-generalization shape, one level up.** The
table already widened this once — from "dbt manifest" to "pluggable provider: dbt metadata, file
tags, sidecar manifest, or MIP/Purview" — before a single provider is built and before the one real
consumer's own proposal (`qbiz_dbt_startup_kit`'s `DATA_SENSITIVITY_PROPOSAL.md`) has team sign-off.
Build the dbt manifest provider concretely against that real consumer first, wire J2 (redaction) to
it end-to-end, and generalize to a provider *interface* only once a second concrete provider
(document/folder tags, say) exists to abstract from. Designing the interface now, against
MIP/Purview integrations nobody has started, is guessing twice removed from evidence.

**D8, D2, D5, D6 — no argument, these are sized right.** Safe defaults exist and cost nothing to
leave as-is (MID-until-benchmarked, skip-memory-until-shared, regex-first, fail-closed-default).
Correctly not on the critical path.

**D9 — this is the one to point at as the model for the others.** Module-not-tool, wrap an existing
rule corpus instead of authoring one, split only on a named trigger with a cheaper alternative
recorded first. That's exactly the reasoning I'd want applied to D4 and D7 above, and the plan
already knows how to do it here — it just didn't carry the same discipline to those two.

---

## 2. Component "still to specify" items

**Two of these are stale — the plan hasn't caught up to its own shipped code.**

- **Component 6's "still to specify" list still names per-tool timeouts** ("a global 30s is wrong
  for most tools — timeouts belong on the tool, not the wrapper"). But `orchestration.py`'s
  `with_retry(timeout=30.0)` already takes `timeout` as a call-site parameter, and the plan's own
  Phase 1 checklist says so ("Done — per-call timeout is a call-site arg"). The Component 6 section
  text contradicts the plan's own phase tracker. Fix: drop that bullet, leave partial-success
  recovery and deadlock handling as the genuinely open items — those are real and unaddressed.

- **Component 8's "still to specify" list is vaguer than the actual gap.** It says "unattended/
  overnight behavior" — but D6 already answers that (fail-closed default for HIGH+ *is* the
  overnight-safe answer). The real open item is more specific and isn't named: `TimeoutPolicy.ESCALATE`
  raises `HitlEscalationRequired` and nothing catches it yet — there is no paging mechanism, no
  "secondary contact" concept anywhere in the code. Escalate is currently a policy name with fail-
  closed's behavior and a different exception type, not a functioning third option. That's worth
  stating plainly instead of under a fuzzier heading, because it's the kind of gap that looks closed
  in a demo (the exception is raised, tests probably assert that) and isn't closed in practice
  (nobody gets paged).

**Component 2's "downstream compatibility beyond shape" note is correctly scoped down** — good call
pushing factual consistency to the evaluator rather than trying to fake semantic checking with
rules. No pushback.

**Component 1's "safety instructions as versioned config" is correctly low-priority** — it's cheap
whenever it happens and gates nothing. Leave it where it is in the queue.

---

## 3. Fleet Operation — manifest & config inheritance

The three-layer inheritance (org defaults → cohort template → per-cohort override) is argued from
precedent (omnigent's stacked scopes) but the plan never specifies **merge semantics** — does a
cohort override replace a dict wholesale, deep-merge it key-by-key, or replace-with-append for list
fields like `action_limits`? That's not a detail to leave implicit. Silent merge-semantics bugs in
a fleet permission resolver are exactly the class of thing that's hardest to debug in front of a
client (a cohort silently inherits a permission nobody meant it to keep, or silently drops one an
override was supposed to add to rather than replace). This needs a one-paragraph spec before
anyone writes the resolver, and it's a cheap ask — not new scope, just naming what "layered policy"
has to mean concretely.

Once that's named, my recommendation is to build the *narrowest* version first: **replace-at-top-
level-key**, no deep merge. A cohort's `models.yaml` either inherits the template's bands wholesale
or fully overrides them per activity key — no partial-field merging inside a single activity's
`ActivityBand`. That's a resolver small enough to hand-verify (walk three files, print the merged
result), not a policy engine. At ~12 cohorts, replace-at-key covers the actual duplication problem
the plan is solving (one HIGH template, not twelve copies) without building general-purpose
deep-merge machinery for a scale (hundreds of cohorts, deeply nested per-field overrides) nobody has
today. If a real cohort later needs to override one field of an inherited activity band without
restating the whole thing, add deep-merge then, against that real case — not against the 12-cohort
case in front of us now.

---

## 4. Data Sensitivity (J1–J9) — this is where I pushed hardest

Nothing here is built, which the plan is upfront about, and the honesty about what
`default_confidential` does and doesn't promise (a coverage guarantee, not a correctness one) is
exactly right and I'm not touching it — that's earned rigor, not decoration, because the failure
mode it's guarding against (a redactor that "retires the client's own caution") is real and the
plan names it correctly.

**Where I'd change the plan:**

**J9 belongs in Phase 1, not Phase 2.** The plan already says J9 needs no `[D1]` and should ship
first within Phase 2. But look at why Phase 1 items shipped first: they're agent-agnostic,
config-only, no per-agent prerequisites. J9 (a static per-run egress allowlist) is exactly that
shape — it has *more* in common with `cost_governor.py` and `model_policy.py` than it does with
Component 1 (input wrapper), which it's currently scheduled behind. There's no dependency forcing
J9 to wait for the input wrapper. Move it into Phase 1's already-shipped batch (or declare a
Phase 1.5 for it now) — it's the single cheapest, strongest control in the whole data-sensitivity
section by the plan's own "Where the boundary actually is" ranking, and there's no technical reason
it's waiting.

**J3 is cheaper than the plan's sequencing implies, and should be called out as a near-free
increment alongside J2/J7/J8/J9.** `output_validator.py`'s `check_scope()` already implements
exactly this shape today — "flag anything referenced that isn't in the permitted set." J3
("classified-data leak detection in output") is the same function signature with `referenced_systems`
swapped for "values sourced from restricted columns." Once J6 (classification lookup) exists, J3 is
close to a direct reuse of code that's already shipped and tested, not new design. The plan lists
J2/J7/J8/J9 as the "sensible first deliverables" and leaves J3 unmentioned in that set — I'd add it;
it rides the same output-validator pattern that's already proven.

**The attestation ledger (J7/J8) is being fully spec'd — hash-keyed clearance, expiry, scope,
bulk glob/label attestation, derived-content inheritance — before a single line exists.** The
sizing section itself admits this is likely "the bulk of" the whole data-sensitivity build. I'm not
arguing against any individual piece — hash-keying so an edit invalidates clearance, and
derived-content inheritance so local extraction can't launder confidential content, are both real:
skip either and the control has a hole a determined (or just lazy) user finds immediately. That's
necessary complexity, not decoration, and cutting it would produce exactly the false-confidence
failure mode the section is trying to prevent.

What I would cut is the sequencing: build human-attested-only, single-scope, no-expiry,
no-bulk-attestation first, against one real engagement, and confirm the refuse-not-redact shape
actually works in practice before adding expiry semantics, glob/label bulk scoping, and multi-scope
resolution on top. The plan is right that per-file attestation "does not survive contact with an
inventory engagement" — but that's a prediction, and the cheapest way to find out which of expiry /
bulk / derived-inheritance an engagement actually stresses first is to ship the minimal version and
watch it get used, not to design all four dimensions up front against no usage data at all. This is
the same "build last, rubric depends on seeing real outputs" logic the plan already applies to the
evaluator (Component 7) — apply it to the ledger too.

**J1/J5/J6 correctly wait on D1/D7 — no argument.** J4 (audit schema fields) is genuinely trivial
(additive fields on an already-additive schema) and needs no separate discussion.

---

## 5. Implementation Order — sequencing calls

Endorse the overall shape: decision-independent work first, decision-gated work correctly blocked,
evaluator deliberately last because its rubric needs real output to design against. Two changes:

1. **Pull J9 into Phase 1** (argued above — it's agent-agnostic and has zero prerequisites, same
   shape as everything else that shipped there).
2. **Narrow Phase 7's D4 item to "interface + JSONL," not "interface + SQLAlchemy fallback."**
   Building the SQLAlchemy MySQL/Postgres path speculatively, before a client without a suitable
   warehouse has actually shown up, is the same premature-abstraction issue as the D4 discussion
   above. The plan already has a bucket for exactly this kind of thing — *Deferred Concerns*, "real
   but not load-bearing yet, addressed when a concrete use case forces them." I'd move the
   SQLAlchemy fallback there and keep Phase 7 to the writer interface plus JSONL, which is all that
   demo and near-term work actually needs.

---

## What I'm *not* proposing to cut

Worth stating plainly, since this role reads as reflexively anti-complexity if I don't: the
model-tier policy's construction-time evaluator-band validation, the audit log's fleet schema
(`event_type`/`incident_id`/`cohort`/`job_id` as additive optional fields), and the
refuse-not-redact posture of the admission gate are all complexity that's paying for itself against
a real, named failure mode, not complexity for its own sake. None of those are on my cut list. The
pattern across everything I *did* flag is the same one: full designs being written against
consumers, providers, or engines that don't exist yet, in sections of the document that are
otherwise honest about being unbuilt. Build the narrow real thing first; generalize from the second
real case, not the first imagined one.
