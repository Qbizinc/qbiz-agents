# Assay recommendations prioritization — working artifacts

*2026-08-07. Design of a Priority × Effort matrix capability for `assay/`. Four plan drafts, two
rounds of blind Engineer + Challenger review.*

**Superseded working material. Not authoritative.** The design that shipped is the
"Recommendations prioritization" section of
[`assay/ASSAY_PLAN.md`](../../../assay/ASSAY_PLAN.md) — *designed, not built, behind a review
gate.* The retrospective on how the process itself performed is
[`findings/2026-08-07-assay-prioritization.md`](../../findings/2026-08-07-assay-prioritization.md).

## What to read first

If you are about to work on this feature, read `ASSAY_PLAN.md`, not this folder. Come here only to
answer *"why was X ruled out?"* — most of the expensive analysis is in the reviews, not the plans.

Highest value per minute: **`REVIEW_challenger_v3.md`** and **`REVIEW_engineer_v3.md`**. They
contain the arithmetic that killed v3 and the argument that cut an entire abstraction layer.

## Lineage

| File | What it is |
| --- | --- |
| `PRIORITY_MATRIX_PLAN.v1.md` | First draft. Per-finding Priority × Effort, median-split quadrants. |
| `REVIEW_engineer.md` | Round 1, Engineer. Effort reduces to a function of `finding.offering`; false "this is free" claims; the `Finding.key` prerequisite. |
| `REVIEW_challenger.md` | Round 1, Challenger. Same collapse found independently by arithmetic over the demo report; the "second axis is our own price list" critique. |
| `PRIORITY_MATRIX_PLAN.v2.md` | Regrained to workstreams. **Never reviewed** — superseded before round 2. |
| `PRIOR_ART_urgent_strategic.md` | Transcription of a prior engagement's methodology slide (Urgent × Strategic, P0–P3 contour bands), with curvature confirmed against the original. Drove the v3 redesign. |
| `PRIORITY_MATRIX_PLAN.v3.md` | Axis registry, contour bands, derived grain. |
| `REVIEW_engineer_v3.md` | Round 2, Engineer. Axis registry is speculative generality; the id problem was moved, not solved; sizing ~2× low. |
| `REVIEW_challenger_v3.md` | Round 2, Challenger. **v3's default config reproduces a plain severity sort**; the unset-axis incentive inversion; the contour-vs-cost-axis error. |
| `PRIORITY_MATRIX_PLAN.v4.md` | Final draft. Folded into `ASSAY_PLAN.md`. Itself unreviewed. |

## The three findings worth not re-deriving

1. **v3's default configuration produced a severity sort.** With `urgent` derived from severity,
   `strategic` unset and degrading to the derived axis, the band thresholds map back onto
   `Severity` as an exact bijection over the demo's 13 findings — roughly 900 lines to reproduce a
   one-line sort. Verified independently before the redesign.
2. **The contour crossover is `p ≥ 2.409`, not 2.** `2^(-1/p) ≥ 0.75`. Both reviewers derived this
   blind to each other. A plan claiming "shape ≥ 2 is sufficient" is wrong.
3. **A contour is valid for two *value* axes and invalid against a *cost* axis.** "Extreme on one
   axis suffices" makes a zero-impact trivial task outrank an important hard one — verified at
   0.717 vs 0.474. The prior-art slide is the proof of the distinction, since both of its axes are
   values.

## Caveats

Every draft here was written by the Architect persona, which also reconciled both review rounds —
the author-plus-reconciler conflict is the main methodology finding in the retrospective, and it
applies to this folder's contents. The reviews are the independent material; the plans are not.

`PRIORITY_MATRIX_PLAN.v2.md` was never reviewed by anyone and should not be read as vetted.
