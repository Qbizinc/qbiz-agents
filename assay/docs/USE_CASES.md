# Assay — business use-case sheet

*For engagement managers and anyone scoping discovery work with a prospect or client.
Technical docs: [../README.md](../README.md); how to extend it: [EXTENDING.md](EXTENDING.md).*

## What it is

Assay is an internal Qbiz tool that scans a client's data estate and produces a scored,
evidence-backed **Data & AI readiness report**. Every finding in the report is a parsed fact
("14 of 20 models have no tests"), not an opinion, and each one names the Qbiz engagement
that would fix it — so the report doubles as a proposal skeleton.

It exists because most prospect conversations now include some version of "we want to use AI
and we're not sure we're doing it right." Assay turns that conversation into a concrete,
defensible document in about an hour of the prospect's time.

## What you can do with it today

- **Run a pre-sales "pulse check" from three shareable files.** A dbt `manifest.json`, a copy
  of their Airflow DAG folder, and read access to a code repo. Any subset works — the report
  honestly marks what couldn't be assessed. **No credentials, no system access, nothing
  installed on their side.** That constraint is enforced by the tool, not just promised, which
  is a useful thing to be able to say to a cautious prospect.
- **Hand the client a readable deliverable.** A scorecard across six readiness dimensions
  (data quality, documentation, governance & data sensitivity, operations, cost, AI
  governance), findings with severity and specific remediation, and a roadmap that groups
  findings by the Qbiz offering that retires them, highest-risk first.
- **Show, not tell, the governance story.** The report's final section discloses how it was
  produced: the assessment itself runs under the Qbiz agent harness — cost-capped, bounded,
  fully audited — and the report prints those numbers. "The document you're holding was
  produced by a governed agent" is a working demo of what we sell.
- **Adapt it to the client in minutes.** One config file per engagement: reweight dimensions
  to match what the client cares about, rename them to their vocabulary, apply their standards
  in place of our defaults. No development work involved.
- **Add checks for a client's specific stack quickly.** A new check (a different orchestrator,
  a BI tool, a connector audit) is a small piece of Python any of our consultants can write —
  the target is under a day, most in an hour or two. Checks built for one engagement stay in
  the library, so discovery gets faster with every engagement that uses it.

## What it actually checks today

Concretely, the current checks find: untested and undocumented dbt models, sources with no
freshness SLAs, missing data-sensitivity classification, DAGs with no retries / no failure
notifications / no owner, unbounded backfill configurations (surprise compute spend), LLM
usage with no cost caps or audit trail, and hardcoded credentials in code. An AWS security
posture check (public buckets, unencrypted storage, over-broad IAM policies) is built and
tested but needs the live connection wiring that ships in the next phase.

## Honest limitations

- **Scores are not yet calibrated against real engagements.** Bands and weights are sensible
  defaults. Use scores to rank problems and structure the conversation; don't quote "you're
  a 61" as if it were benchmarked. Calibration is an open item.
- **Artifact-based checks only, for now.** Connected checks that query live systems
  (warehouse spend analysis, cloud posture, AI provider spend) and interview-based dimensions
  (organizational siloing, governance process) are designed and on the roadmap, but not
  runnable against a client yet.
- **It is read-only and never will fix anything.** By design — remediation is the engagement.
- **Report prose is template-generated,** not LLM-written, in the current build. The facts and
  scores are the substance; the narrative layer is deliberately plain.
- **It sees what the artifacts show.** A great data team with artifacts we don't parse yet
  will under-score; the "not assessed" markers keep that honest, but read the report before
  forwarding it.

## What to ask a prospect for

Any of: their dbt project's `target/manifest.json` (one file, produced by a command they run
daily), a copy of their Airflow DAGs folder, read access to a data/ML repo. One is enough to
start; three gives the full current picture.

## Running one

Consultant-run, one command, a few minutes of machine time. Talk to David Sevier (Data & AI)
to get an assessment run or to get set up to run them yourself.
