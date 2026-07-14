# Synthetic client fixtures

Everything under this directory is a **fabricated client estate** ("Acme Analytics") used
by Assay's demo and tests. None of it is real: the companies, pipelines, models, and —
importantly — the **credentials are all fake**.

The fake hardcoded credentials (an `EXAMPLE`-patterned API key, a `hunter2`-style FTP
password) are here *on purpose*: Assay's credential scanner has to find something. This
path is allowlisted in the repo-root `.gitguardian.yaml` for exactly that reason.

Rules if you add fixture material (from SECURITY.md):

- Fake credentials must be **obviously fake on sight** — `EXAMPLE` keys, joke passwords.
  Never a real credential with one character changed, never anything from a real system.
- Keep them minimal: one per credential *shape* the scanner must detect.
- New fixture directories outside this one need their own `.gitguardian.yaml` entry and
  README, in the same PR.
