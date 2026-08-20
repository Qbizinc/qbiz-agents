# Instructions for agents

This folder holds reusable role definitions: [Architect.md](Architect.md), [Engineer.md](Engineer.md),
[Challenger.md](Challenger.md), [Editor.md](Editor.md), [Project-Manager.md](Project-Manager.md),
[QA.md](QA.md), [Reviewer.md](Reviewer.md), [Fact-Checker.md](Fact-Checker.md),
[Product-Manager.md](Product-Manager.md), [Advocate.md](Advocate.md), [Researcher.md](Researcher.md),
[Scientist.md](Scientist.md), [Auditor.md](Auditor.md). See [README.md](README.md) for what each role
is for.

**Before writing a design-review, plan-critique, or multi-perspective prompt from scratch — check
here first.** If the task matches one of these roles, read the file and adopt it verbatim rather
than improvising an equivalent persona inline. Do not summarize or compress a persona file into a
shorter prompt; read it in full and use the behavior and boundaries as stated.

For a design decision or PR review of real weight, prefer a reconciled multi-role review over a
single undifferentiated pass: pick one role as **Lead** — whichever domain the decision actually
turns on — and one or more other roles as **Drafters**, chosen for the lenses the decision actually
needs, not by default. Architect leading Engineer and Challenger is the validated worked example (see
`README.md`), not the only correct shape. A review of whether something should be built at all is
better led by Product Manager, calling in whichever drafters the specific question needs — Advocate if
it has consequences outside the room, Challenger if the framing itself is suspect, QA if the real risk
is untested coverage, and so on. Whoever leads reconciles disagreement between the drafters, the same
way Architect does in the worked example — that is a property of being designated lead for this pass,
not something written into every role's own file. Only Architect's file states standing ruling
authority; naming another role Lead for a review doesn't require, and shouldn't prompt, editing that
role's file to match.

If you are delegating to a subagent to fill one of these roles, pass it the persona file's content
(or its path, if the subagent can read files) — don't just pass the role's name.

## Running the pattern

Once Lead and Drafters are picked, follow this shape rather than an ad hoc version of it — validated
against a real review with Architect leading Engineer and Challenger; see `README.md`'s worked example
for what each step caught and why it mattered. The mechanics below generalize past that specific trio:

1. **Scope to what's actually open.** If the artifact under review has its own settled or shipped
   sections, exclude them explicitly — don't let a drafter re-litigate them.
2. **Drafters draft independently, blind to each other.** Separate subagents, launched in parallel,
   no sibling visibility, however many drafters the review calls for. Anchoring on a sibling's draft
   defeats the point of asking more than one role instead of one.
3. **Ground every draft in the real artifact, not just the document describing it** — the code, not
   only the plan; the diff, not only the PR description.
4. **Output to a clearly-scratch location.** Never let a draft overwrite the thing under review.
5. **The Lead reconciles only — it does not also submit a competing draft.** A Lead that drafted and
   then judges its own entry has a conflict of interest, whichever role is filling the seat.
6. **Verify, don't just trust, any code- or fact-level claim** in any draft before ruling on it.
7. **Order the ruling by whatever priority the Lead role's own file states as primary** — Architect's
   is consequence and reversibility; a different Lead orders by its own stated priority instead, not
   by the order things appear in the source.
8. **If findings get applied to the real source, tag every changed line with a provenance marker**
   so its origin is greppable later.
