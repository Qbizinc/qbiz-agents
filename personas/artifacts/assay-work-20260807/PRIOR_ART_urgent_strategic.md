# Prior art — "Recommendations Prioritization: Methodology"

*Slide from a previous QBiz client engagement, surfaced by David 2026-08-07. Transcribed by the
Architect because subagents cannot be shown the image. This is a faithful description, not an
interpretation — interpretation lives in `PRIORITY_MATRIX_PLAN.v3.md` §0.*

**Provenance caveat (open item [A13]):** this slide establishes that the methodology was
*presented* to a client. It does **not** establish that it was used, that it worked, or that it is
a QBiz house standard. Treat it as one data point, not as authority.

---

## The chart

A single plot occupying the right two-thirds of the slide.

- **X axis:** labelled **"Strategic"**, arrow pointing right. No numeric scale, no tick marks.
- **Y axis:** labelled **"Urgent"**, arrow pointing up. No numeric scale, no tick marks.
- **Neither axis is effort, cost, or size.** Both are value/priority-style axes.

Three blue curves sweep across the plot area, dividing it into four bands. Each curve runs **mostly
but not entirely flat** along the left side — declining gently — then bends downward and falls
steeply as it approaches the right edge. A superellipse quadrant / iso-value contour.

**Curvature confirmed by David, 2026-08-07**, who has the original slide: both "convex toward the
origin" and "flat, then plunging at the right edge" describe the real curve, and the flatness is
*partial* — there is a gentle decline across the left portion, not a plateau.

**What that pins down.** A perfectly-flat-then-vertical boundary would be `max()` (p → ∞). A gentle
decline steepening into a plunge is a **finite** shape parameter, roughly p ≈ 3–5. So:
- "Extreme on one axis alone is sufficient" is confirmed as the intent, but as a strong tendency
  rather than an absolute — a genuine trade-off exists across the whole range.
- `shape` is a real tunable parameter, not a degenerate case to be hardcoded.
- p sits above the 2.409 crossover at which a lone maximum-urgency item reaches the top band
  unaided (see `PRIORITY_MATRIX_PLAN.v4.md` §4.3).

The four regions are labelled, from the top-right corner inward toward the bottom-left:

| Band | Position |
| --- | --- |
| **P0** | top-right region, outside the outermost curve |
| **P1** | between the outer and middle curves |
| **P2** | between the middle and inner curves |
| **P3** | bottom-left region, inside the innermost curve |

**The key geometric property:** because each curve runs out to meet *both* the top edge and the
right edge, an item that scores extremely high on **one** axis alone lands in P0 without needing a
high score on the other. A straight-line 2×2 quadrant split cannot express this; these contours do
it natively.

## The text (left third, verbatim)

> **Evaluate Priority**
> - Based on dimensions of Urgency and Strategic value
>   - Flexibility to work with client based on their feedback
> - Most significant challenges
>   - Data Confidence
>   - Development Velocity
>   - Cost Efficiency
>   - Security Risk
> - Data Management categories
>   - Architecture & Design
>   - Risk & Compliance
>   - Policy & Process
>   - Cost Optimization
>   - Infrastructure & Tooling

## Notes on the text

1. **"Flexibility to work with client based on their feedback"** — the axes and the banding are
   explicitly negotiable *with the client*, in the room. This reads as a facilitation instrument
   used in a workshop, not a scoring engine that emits a fixed answer.
2. **The two lists are not axes.** "Most significant challenges" (4 items) and "Data Management
   categories" (5 items) appear to be tagging/grouping vocabularies for the recommendations being
   plotted — closer in kind to Assay's *dimension registry* than to anything on the X or Y axis.
3. The deck slide is titled "Recommendations Prioritization," so the plotted items are
   **recommendations** — remediation proposals — not raw findings and not tasks.
