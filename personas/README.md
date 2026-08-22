# Personas

Reusable role definitions for agent and subagent work across Qbiz projects. Use these instead of
reinventing a review or work persona from scratch each time.

Lives in `qbiz-agents` for the same reason `checks/` does: it's reference content read directly by
agents working anywhere in the Qbiz ecosystem, not a skill that gets installed via the `qba` CLI —
this repo is the shared home for exactly this kind of reusable material. See the root
[README.md](../README.md#personas) for how this fits alongside skills, bundles, and checks.

## Roster

- **[Architect](Architect.md)** — leads design and review; rules on disagreements between the
  other two; weighs consequence and reversibility before anything else.
- **[Engineer](Engineer.md)** — implements; argues feasibility and cost; pushes back on
  over-engineering harder than anyone else.
- **[Challenger](Challenger.md)** — finds the alternative nobody listed; questions the framing;
  looks for how something can be broken, misused, or abused.
- **[Editor](Editor.md)** — judges register and audience fit; catches hedging once a tone is picked;
  asks whether this sounds like what it's trying to be, to whoever it's for.
- **[Project Manager](Project-Manager.md)** — judges timing, failure shape, and whether something
  reads as done; tracks threads that resolved, stalled, or got dropped without a trace.
- **[QA](QA.md)** — checks coverage: is this true everywhere it should be, not just where someone
  happened to look; a directed sweep, not exploratory.
- **[Reviewer](Reviewer.md)** — the first-look read, deliberately carrying no standing context; says
  what only shows up to someone seeing it cold.
- **[Fact-Checker](Fact-Checker.md)** — checks a specific claim against its actual source; catches
  self-contradiction and claims that sound right but aren't.
- **[Product Manager](Product-Manager.md)** — gates work before it starts: does this need to exist,
  is the goal stated plainly, do the requirements and the plan actually reach it.
- **[Advocate](Advocate.md)** — speaks for whoever isn't in the room and for what a decision quietly
  sets as precedent, with no authority of its own beyond naming it.
- **[Researcher](Researcher.md)** — checks for reuse and precedent before anything new gets built;
  reports sources and disagreement between them rather than picking quietly.
- **[Scientist](Scientist.md)** — designs the measurement: freezes ground truth and the exit
  condition before the run, and writes up a null result with the same weight as a win.
- **[Auditor](Auditor.md)** — read-only check on whether a record asserts something it never
  actually observed; flags, verified and severity-graded, never fixes.

**Researcher, Scientist, and Auditor are provisional strip-downs** — no full persona exists yet for
any of the three (see `Agents/Agents-Extended.md`), so these are the review-question layer built
directly rather than stripped from an existing character. Useful for testing what each lens actually
catches before committing to a full personality; a real persona built later still has to clear the
conditions already on record for it (Scientist's three pre-registration sentences, Auditor queued
behind her) regardless of how this stripped version performs.

## When to use

- **Single persona** — adopt one voice for a task in character. E.g. have a subagent implement as
  Engineer, or review a plan as Architect.
- **Reconciled multi-role review** — pick one role as Lead and one or more others as Drafters, based
  on what the decision actually turns on, and have the Lead rule on disagreement between the
  Drafters. Architect leading Engineer and Challenger (below) is the validated worked example, not
  the only shape — a necessity-gating review is better led by Product Manager, for instance. Reach
  for this on any nontrivial design decision or PR review instead of a single undifferentiated pass.
  See [AGENTS.md](AGENTS.md) for the mechanics the pattern was validated against.

## How to use

Read the relevant persona file(s) in full and adopt the stated behavior and boundaries — don't
paraphrase or summarize them into a shorter prompt. Every role shares one rule that overrides
everything else in its file: **role never overrides correctness.**

## Worked example: the harness plan review (2026-08-06)

First real run of the three-role pattern, against `harness/HARNESS_PLAN.md` — a live ~1300-line
planning document, not a toy exercise. Recorded here as *a* reference shape, not *the* shape — this
is one working example, not the only correct way to run the pattern. Use the judgment behind each
step (why it was scoped, why the drafts were blind, why Architect didn't also draft) over the letter
of it when a different situation calls for a different structure.

**Structure:**

1. **Scoped to what was actually open before drafting.** The plan has its own "Decisions Locked"
   section marked don't-relitigate. Review was confined to the open ground (the Required Decisions
   table, per-component "still to specify" items, the Fleet Operation design, the unbuilt Data
   Sensitivity section) — everything locked or already shipped was fixed context, not a target.
   Re-arguing settled ground produces noise, not signal.
2. **Engineer and Challenger drafted independently and blind.** Two separate subagents, launched in
   parallel, neither could see the other's draft. Both were required to ground themselves in the
   actual shipped code, not just the plan's prose — the plan is aspirational in places and ahead of
   (or behind) the code. Each wrote a full proposal to a clearly-scratch location, never touching the
   real plan file, and reported back only a short summary to keep the parent conversation light.
3. **Architect did not also draft.** The first version of this test had Architect write a third
   competing proposal and then judge all three, including its own — a conflict of interest, since
   nothing then stops the "review" from rubber-stamping the position it already committed to in
   writing. Revised structure: Architect's only output is the reconciliation of the other two.
4. **Architect verified code claims before ruling, not just trusted the prose.** Both drafts made
   specific claims about the real implementation. Before ruling on either, the actual source was
   read and each claim checked directly — a review of an implementation is a claim about the code,
   not about what a persona wrote about the code.
5. **Rulings were ordered by consequence and reversibility, not by document section** — Architect's
   own stated priority. A one-word wording fix that kept an oversold claim from reaching a client
   outranked a sequencing preference, regardless of which persona raised it or where it sat in the
   source document.
6. **Findings were folded into the real document with provenance tags**, once asked for — every
   changed line in `HARNESS_PLAN.md` tagged with a consistent marker, so its origin is one grep
   away instead of reading as if the plan always said that.

**Where it showed real value, not just prose polish:**

- **A verified, shipped-code bug** — a retry decorator was silently swallowing and retrying harness
  rejections it should have let propagate immediately. Found because Challenger was required to
  read the actual code, confirmed because Architect re-verified it rather than taking the draft's
  word for it.
- **A client-facing overclaim caught before it shipped** — the plan called one enforcement layer
  "un-bypassable," true against the model but not against an engineer who forgets to wire a guard
  in. Cheap to fix in a planning doc; expensive to walk back after a client heard it.
- **A better answer than either draft alone.** Engineer argued to resolve one open decision now
  (cheap, unblocks downstream work); Challenger argued the decision was framed on the wrong axis
  entirely. Neither was wrong — combined, the resolution was sharper than either would have produced
  solo. That's what reconciling, rather than averaging, is supposed to produce.
- **A place Architect had to actually rule, not just merge.** Engineer wanted to sequence a
  higher-risk section narrow-first; naively adopting that could have silently deferred structural
  fixes Challenger had found along with it. The ruling drew the line between which *dimensions*
  could wait and which *integrity properties* had to ship regardless.
- **Cheap confirmation signal.** Several decisions got independently reviewed by both personas and
  both concluded "already sized right, leave alone." Two independent reviews agreeing nothing's
  wrong is stronger evidence than either alone, and cost nothing extra to obtain.

**When this is worth the cost:** two full independent review passes plus a reconciliation is real
spend, not a free action. Reach for it on a live planning document or a PR with genuine stakes —
against something trivial, the same structure would mostly produce restated agreement.

## Retrospectives and working material

[findings/](findings/) records how the pattern actually performs on real work — what each run
caught, what it missed, what it cost, and which rules should change as a result. **Write an entry
after any substantive multi-role review**; the methodology only improves if outcomes get tracked,
and the useful entries are the ones that name failures rather than successes.

[artifacts/](artifacts/) keeps the working material each run produced — draft plans, reviewer
output, transcribed source evidence — one subfolder per run. None of it is authoritative; it exists
so the reasoning behind a decision survives, particularly the options that were verified and
rejected. A plan records what was chosen; it rarely records what was ruled out and why.

The worked example above (harness plan, 2026-08-06) predates both folders and is recorded here only.

## Adding a new role

The current roster covers most review and work needs, but don't force a task into an existing role if
it genuinely needs a different lens (e.g. a security-specific reviewer). Add a new file rather than
stretching an existing persona's job past what its name says.

Before adding one, check that it's not already covered — a new role should do a job none of the
existing roster does, not a narrower or overlapping version of one.

Match the existing format:

- `# Name`, then a one-line statement of what the role is *for* (not a job title restated).
- `## What you do` — the concrete responsibilities.
- `## How you work` — the working style and disposition, including how it interacts with the
  other roles if relevant.
- `## Boundaries` — what the role does not have authority to do, and end with **role never
  overrides correctness.**

Keep it short — these are meant to be read in full every time, not skimmed. Add the new role to
the roster in this README once it exists.

See [AGENTS.md](AGENTS.md) for the directive agents should follow when landing on this folder.
