# Assay — business use-case sheet

*For engagement managers and anyone scoping discovery work with a prospect or client.
Technical docs: [../README.md](../README.md); how to extend it: [EXTENDING.md](EXTENDING.md).*

## What it is

Assay is an internal Qbiz tool that scans a client's data estate and produces a scored,
evidence-backed **Data & AI readiness report**. Every finding is a parsed fact ("14 of 20
models have no tests"), not an opinion, and each one names the Qbiz engagement that would fix
it — so the report doubles as a proposal skeleton.

It runs in two modes: a deep **full Client Analysis** that anchors a discovery engagement, and
a lightweight **pulse check** that gets us into the conversation. The full analysis is the
main event; the pulse check is the on-ramp.

## Full Client Analysis — the discovery engagement, productized

This is the flagship use. Instead of a discovery phase that's a stack of interview notes and a
consultant's judgment, the client gets a structured, scored, reproducible assessment across
their whole estate — and we get a findings-to-offerings roadmap that writes the proposal.

- **One engagement-grade deliverable across six-plus readiness dimensions** — data quality,
  documentation, governance & data sensitivity, operational maturity, cost efficiency, AI
  governance, and (as we bring live-system checks online) cloud/security posture, warehouse
  and AI spend, and organizational siloing.
- **Every finding maps to a Qbiz offering.** The report's roadmap groups findings by the
  engagement that retires them, highest-risk first. Discovery output *is* the scope of the
  follow-on work.
- **Tuned to the client, not to us.** One config file per engagement: reweight dimensions to
  what the client cares about, rename them to the client's vocabulary, and apply the client's
  own standards in place of our defaults. No development work.
- **Extensible to the client's specific stack.** A check for something we don't cover yet — a
  different orchestrator, a BI tool, a connector audit — is a small piece of Python a
  consultant writes in an hour or two. Checks built for one engagement stay in the library, so
  every engagement makes the next discovery faster and sharper.
- **The deliverable proves the governance pitch.** The assessment itself runs under the Qbiz
  agent harness — cost-capped, bounded, fully audited — and the report's final section prints
  those numbers. "The document you're holding was produced by a governed agent" is a working
  demo of exactly what we sell.

### What the full analysis runs against a client **today**

A deep, artifact-based review: dbt project, Airflow DAGs, and code repositories, tuned per
client and extensible to their stack, producing the full scored report, roadmap, and
governance disclosure. This half is live now.

### What's landing next (in active development, not yet client-runnable)

The live-system and conversational half of the full tier: read-only checks against the
warehouse (spend hotspots, idle compute), cloud/security posture (public storage, over-broad
IAM), and AI provider spend; plus structured interviews for dimensions you can't scan for, like
organizational siloing and governance process. The first connected check — AWS security
posture — is built and tested; it needs the live-connection wiring that ships in the next
phase. Scope these as roadmap when you're setting expectations, not as available this quarter.

## Pulse check — the zero-credential on-ramp

The way we earn the full engagement. A prospect shares a few files; an hour later they have a
real, specific readiness snapshot with our name on it.

- **Runs from three shareable files** — a dbt `manifest.json`, a copy of their Airflow DAG
  folder, and read access to a code repo. Any subset works; the report honestly marks what
  couldn't be assessed.
- **No credentials, no system access, nothing installed on their side** — and that constraint
  is enforced by the tool, not just promised, which is a useful thing to say to a cautious
  prospect.
- **Same deliverable shape as the full analysis**, so the pulse report reads as a preview of
  the deeper engagement rather than a different product.
- Fully runnable today, end to end.

## What it actually checks today

Concretely, the current checks find: untested and undocumented dbt models, sources with no
freshness SLAs, missing data-sensitivity classification, DAGs with no retries / no failure
notifications / no owner, unbounded backfill configurations (surprise compute spend), LLM
usage with no cost caps or audit trail, and hardcoded credentials in code. The AWS posture
check listed above is built and tested but awaits live-connection wiring.

## Honest limitations

- **The full tier's live-system and interview checks aren't client-runnable yet.** Warehouse
  spend, cloud posture, AI spend, and interview-based dimensions are designed and in active
  build. Today the full analysis is a deep *artifact* review; sell the live-system depth as
  near-term roadmap, not current capability.
- **Scores are not yet calibrated against real engagements.** Bands and weights are sensible
  defaults. Use scores to rank problems and structure the conversation; don't quote "you're a
  61" as if it were benchmarked. Calibration is an open item.
- **It is read-only and never will fix anything.** By design — remediation is the engagement.
- **Report prose is template-generated,** not LLM-written, in the current build. The facts and
  scores are the substance; the narrative layer is deliberately plain.
- **It sees what the artifacts show.** A strong team whose artifacts we don't parse yet will
  under-score; the "not assessed" markers keep that honest, but read the report before
  forwarding it.

## What to ask a prospect for

Any of: their dbt project's `target/manifest.json` (one file, produced by a command they run
daily), a copy of their Airflow DAGs folder, read access to a data/ML repo. One is enough for
a pulse check; all three plus a scoping conversation is the start of a full analysis.

## Running one

Consultant-run, one command, a few minutes of machine time. Talk to David Sevier (Data & AI)
to get an assessment run or to get set up to run them yourself.
