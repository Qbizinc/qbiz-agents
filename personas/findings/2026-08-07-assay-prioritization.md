# Assay recommendations prioritization — three-role review retrospective

*2026-08-07. Subject: designing a Priority × Effort matrix capability for `assay/`. Four plan
drafts, two rounds of blind Engineer + Challenger review. Written by the Architect, who was also
the author of every draft — see [The main gap](#the-main-gap-the-architect-was-also-the-author),
which is the most important finding here and the one most likely to be self-servingly understated.*

---

## What happened

| Stage | Output | Result |
| --- | --- | --- |
| v1 | Architect draft: per-finding Priority × Effort, median-split quadrants | Both reviewers found the effort axis carried no information |
| v2 | Regrained to workstreams | Never reviewed — superseded before round 2 |
| — | Prior-art slide surfaced (Urgent × Strategic, contour bands) | Forced a redesign |
| v3 | Axis registry, contours, derived grain | **Round 2 found its default config shipped ~900 lines to reproduce a severity sort** |
| v4 | Hybrid strategic input at dimension grain, axis registry cut | Folded into `ASSAY_PLAN.md`, unreviewed, behind a review gate |

**Cost:** 4 subagent runs, ~397k subagent tokens, 86 tool calls, ~22 minutes wall clock (rounds ran
in parallel internally). Against that: the design it prevented was independently costed at
~1600–2100 lines of code that would have produced a severity sort.

## What worked

### Independent convergence is evidence, not opinion — and it happened twice

The single most valuable property of the method. Both reviewers ran blind to each other, and twice
landed on the same finding by different routes:

- **Round 1:** Engineer reasoned from the data model that effort reduced to a pure function of
  `finding.offering`. Challenger reached the same conclusion by running the arithmetic over the
  13 findings in the shipped demo report.
- **Round 2:** both independently derived that the plan's claimed contour threshold was wrong, and
  both produced the same corrected crossover value to three decimals (2.409). Neither could have
  copied the other.

A single reviewer, however good, gives you an assertion. Two blind reviewers agreeing gives you
something much closer to proof — and it is what made it possible to accept a fatal finding quickly
instead of arguing with it. **This is the return the whole method exists to produce.**

### Grounding reviewers in real code and real fixtures, not just the document

Every prompt required verifying claims against the actual source, and both reviewers were pointed
at real artifacts (the demo report, the collectors, the harness modules). This caught things a
document review structurally cannot:

- The plan claimed a config merge would come free from existing machinery. It would not — the
  existing override code is bespoke per-section.
- The plan claimed a harness component was available. It ships, but is `async` while the consumer
  is synchronous throughout, and no implementation of its transport protocol exists in-repo.
- The plan's identity scheme collided between two findings emitted by the same collector.

**Challenger computing over the real demo fixture was the highest-value single technique across
both rounds.** It converted "I think this collapses" into "here are the 13 values and here is the
bijection." Make it standard: give the Challenger a real dataset and ask it to run the proposed
algorithm over it.

### Showing each reviewer its own prior review in round 2

Round 2 asked each reviewer to check whether its round-1 findings had been handled honestly. This
caught two things nothing else would have:

- A prerequisite dropped twice with no counter-argument and omitted from the not-adopted list.
- A set of mechanisms **hollowed out while keeping the headline** — the section still named the
  concern, but four of its five specified behaviours were gone.

Documents absorb criticism cosmetically. Without the reviewer holding its own prior text, that is
close to undetectable.

### Requiring a "not adopted, and why" section

Forcing the reconciler to list rejected proposals with reasons is what made the above check
possible, and it preserved the cheapest alternative — render the grid, let the room place the items,
~1/5 the code — which survived into the shipped plan as the named fallback. Without that rule it
would have been silently dropped at v2 and rediscovered, if ever, during build.

### Scoping settled decisions out

Each prompt listed the owner's settled decisions and forbade re-arguing them. Neither reviewer
wasted a round on them, and both still critiqued the *execution* of those decisions freely. Cheap
rule, worked exactly as `AGENTS.md` says.

## What did not work

### The main gap: the Architect was also the author

`AGENTS.md` rule 5 says the Architect reconciles and does not submit a competing draft. It does not
cover the case that actually occurred: **the Architect wrote the thing under review, and then
graded the reviews of its own work.** Across this exercise the same role authored v1–v4,
transcribed the only external evidence, and ruled on both review rounds. Both reviewers flagged it
independently.

Concrete damage, not hypothetical:

- A prerequisite raised in round 1 was dropped **twice**, without a counter-argument, and left off
  the not-adopted list. It was correct and is now in the shipped plan.
- Specified mechanisms were reduced to a headline while the section kept its title.
- Size was estimated at 500–700, then 800–1000, against an independent estimate of 1600–2100. Two
  low estimates in the same direction is a bias, not an accident.
- An ambiguity in the Architect's own transcription of the external evidence was resolved toward
  the Architect's design without flagging it. (The owner later confirmed the transcription was
  fine — but the *process* had no mechanism to catch it if it hadn't been.)

**Rule change proposed for `AGENTS.md`:** extend rule 5 from "does not also draft" to "does not
reconcile reviews of its own draft." Where that is unavoidable — as here — the prompt must name the
Architect as the author explicitly, and the reviewers must be told, so they can calibrate. Round 2
did this and immediately produced sharper criticism than round 1.

### Blindness was instruction-only, not mechanical

Both reviewers wrote into the same scratch directory, so each *could* have read the other's review.
They were told not to and there is no sign either did — but that is trust, not enforcement.
**Fix:** separate output directories per reviewer, or don't co-locate drafts until the reconciler
merges them.

### The verification burden lands entirely on the conflicted party

The reconciler verifies the reviewers' claims — and the reconciler is the author. In this case
every load-bearing claim was checked and the checks are recorded, but the method has no independent
check *on the reconciler*. This is the structural weakness behind every item above.

### Review rounds ratchet scope upward

Each round found real problems, and fixing real problems adds code. v1's estimate grew through v3
before v4 cut it back. The corrective did not come from the process — it came from explicitly
asking the Challenger "is the framing itself right?" and the Engineer "is this over-built?", which
produced the two most valuable outputs of round 2: a cut of an entire abstraction layer, and a
~200-line alternative to a ~1000-line design.

**Rule change proposed:** make *"should this be built at all, and is it over-built?"* a mandatory
question in both reviewer prompts, not an optional one the Architect remembers to include. Reviews
default to improving the thing in front of them; someone must be tasked with questioning whether it
should exist.

### Unknown stopping point

We ran two rounds because the owner called it. Round 2 found a disqualifying flaw, which argues
round 3 might have too — but there is no evidence either way, and each round costs real time and
tokens. **No stopping rule exists.** Proposed heuristic, to be tested rather than trusted: stop when
a round produces no finding that changes the design's *shape*, only findings that refine it. By that
test this exercise was not finished, and `ASSAY_PLAN.md` accordingly carries a review gate.

### Two rounds is not a substitute for reviewing the rest of the document

Only the newest section got this treatment. The surrounding plan — older, longer, already partly
built against — has never had it. Easy to mistake a well-reviewed section for a well-reviewed
document.

## Would a single undifferentiated review have done as well?

No, and the evidence is specific. The two roles found substantially **different** things, and
overlapped only on the largest items:

- Engineer found the config-merge cost, the async mismatch, the id collision, and the sizing error
  — implementation-shaped.
- Challenger found the price-list critique, the incentive inversion in the unset axis, the
  contour-versus-cost-axis semantic error, and both structural alternatives — framing-shaped.

Neither list is a subset of the other. And crucially, **the overlap is what carried the most
weight**: a single reviewer reporting "the effort axis carries no information" is a claim to be
weighed; two blind reviewers reporting it from different directions is a finding to be acted on.
The convergence is only available if you run more than one.

## Actions

1. **`AGENTS.md` rule 5** — extend from "does not draft" to "does not reconcile reviews of its own
   draft"; where unavoidable, disclose authorship to the reviewers. *(Not yet applied — proposed
   here, needs the owner's call.)*
2. **Reviewer prompts** — make "is this over-built / should it exist?" mandatory in both roles.
3. **Reviewer prompts** — require running the proposed algorithm over a real fixture where one
   exists.
4. **Multi-round reviews** — give each reviewer its own prior review; ask explicitly whether
   findings were answered or merely absorbed.
5. **Blindness** — separate output paths per reviewer rather than relying on instruction.
6. **Stopping rule** — stop when a round changes only refinement, not shape. Record whether this
   heuristic holds up next time.
7. **Reconciler output** — keep the mandatory not-adopted list; it is what makes round *n+1*
   auditable.

## Caveats on this retrospective

Written by the conflicted party, about a process whose main finding is that the conflicted party
should not be the one writing it. The failures listed are the ones that were caught — by two
reviewers, in two rounds, on one section of one document. Absence of further failures here is not
evidence they are absent.

The draft history and both review rounds were produced in a gitignored scratch directory. They have
since been preserved at
[`../artifacts/assay-work-20260807/`](../artifacts/assay-work-20260807/), so the verified arithmetic
behind rejecting v3 — and the reasoning that cut the axis registry — survives rather than needing
re-derivation. Read the two round-2 reviews there before reopening any of it.
