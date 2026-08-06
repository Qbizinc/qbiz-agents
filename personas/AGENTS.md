# Instructions for agents

This folder holds reusable role definitions: [Architect.md](Architect.md), [Engineer.md](Engineer.md),
[Challenger.md](Challenger.md). See [README.md](README.md) for what each role is for.

**Before writing a design-review, plan-critique, or multi-perspective prompt from scratch — check
here first.** If the task matches one of these roles, read the file and adopt it verbatim rather
than improvising an equivalent persona inline. Do not summarize or compress a persona file into a
shorter prompt; read it in full and use the behavior and boundaries as stated.

For a design decision or PR review of real weight, prefer the three-role pattern over a single
undifferentiated pass: assign Architect, Engineer, and Challenger to separate subagents (or
separate passes by one agent), and have the Architect rule on disagreement between the other two.

If you are delegating to a subagent to fill one of these roles, pass it the persona file's content
(or its path, if the subagent can read files) — don't just pass the role's name.

## Running the three-role pattern

When you run Architect, Engineer, and Challenger together, follow this shape rather than an ad hoc
version of it — validated against a real review; see `README.md`'s worked example for what each
step caught and why it mattered:

1. **Scope to what's actually open.** If the artifact under review has its own settled or shipped
   sections, exclude them explicitly — don't let Challenger re-litigate them.
2. **Engineer and Challenger draft independently, blind to each other.** Separate subagents,
   launched in parallel, no sibling visibility. Anchoring on a sibling's draft defeats the point of
   asking two roles instead of one.
3. **Ground both in the real artifact, not just the document describing it** — the code, not only
   the plan; the diff, not only the PR description.
4. **Output to a clearly-scratch location.** Never let a draft overwrite the thing under review.
5. **Architect reconciles only — it does not also submit a competing draft.** An Architect that
   drafted and then judges its own entry has a conflict of interest.
6. **Verify, don't just trust, any code- or fact-level claim** in either draft before ruling on it.
7. **Order the ruling by consequence and reversibility**, not by the order things appear in the
   source.
8. **If findings get applied to the real source, tag every changed line with a provenance marker**
   so its origin is greppable later.
