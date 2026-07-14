# Secrets policy

How credentials are handled in this repo, and how that's enforced. The short version:
**real secrets never enter the repo, secret-shaped test strings are assembled at runtime,
and one fixture directory is the sanctioned exception.**

## Real secrets

Never committed, in any form, on any branch — including "temporarily" and including
branches that will be squashed. Where they actually go:

- **Local development / MCP servers:** environment variables, usually via `.mcp.json`
  (gitignored) or `.env` / `.env.local` (gitignored). Every MCP server in `mcp/` is built
  to take all deployment-specific config through env — see each server's `SETUP.md`.
- **Client engagements:** the **client's own secrets manager**, whatever it is (AWS Secrets
  Manager, Vault, Doppler, …). Client tokens live in client infrastructure; we don't copy
  them into ours. This is already the rule in `skills/slack-bot-setup/SETUP.md` and applies
  to every connector.
- **CI (when we add it):** repository/organization secrets in GitHub Actions, referenced by
  name — never echoed into logs.

If a real secret does land in a commit: **rotate it immediately** (assume compromised the
moment it's pushed), then remove it from history. Rotation is the fix; history rewriting is
cleanup.

## Secret-shaped strings in tests

Assay's credential detector (and any future scanner we build) needs tests that plant
secret-looking strings. Those strings must **never appear as literals in committed
source** — they get flagged by GitGuardian, and teaching people to dismiss scanner findings
is worse than the finding itself.

The pattern: assemble the string at runtime and write it into a pytest `tmp_path`, so it
only ever exists on disk during a test run. Use `planted_secret_line()` in
`assay/tests/conftest.py`:

```python
from conftest import planted_secret_line

def test_detects_hardcoded_password(self, tmp_path):
    (tmp_path / "script.py").write_text(planted_secret_line("password"))
    ...
```

If you're writing a new suite that needs this, copy the helper's approach (string
concatenation, obviously-fake values), don't invent a new literal.

## The sanctioned exception: `assay/demo/fixtures/`

Assay's demo fixtures are a synthetic client repo whose *purpose* is to contain fake
hardcoded credentials for the scanner to find — they must be committed literals. Rules for
that directory (and any future fixture corpus that earns an entry in `.gitguardian.yaml`):

1. Values must be **obviously fake on sight**: `EXAMPLE`-patterned keys, `hunter2`-style
   joke passwords. Never a real credential "defanged" by one character, never anything
   copied from a real system.
2. The directory must have a README declaring everything in it synthetic.
3. The path must be listed in `.gitguardian.yaml` `ignored_paths` — that file is the
   complete inventory of where literals are allowed.

## Enforcement

Two layers, same engine:

- **GitGuardian GitHub app** scans every PR (org-level; configured in the GitGuardian
  dashboard). Findings appear as PR comments/checks.
- **ggshield pre-commit hook** (`.pre-commit-config.yaml`) catches the same findings
  before they leave your machine. One-time setup:

  ```bash
  pip install pre-commit
  pre-commit install          # from the repo root
  ggshield auth login         # or export GITGUARDIAN_API_KEY=<personal token>
  ```

### When the scanner fires

- **It's a real secret:** stop, rotate it now, then clean up the commit. Do not push.
- **It's a fake needed by a test:** restructure it through the runtime-assembly pattern
  above. Don't dismiss the finding and don't add ignore entries for test code.
- **It's a fixture literal:** confirm it meets the fixture rules above; if the path is new,
  add it to `.gitguardian.yaml` *in the same PR*, with the README.
- **It's a true false positive** (scanner misread something that isn't a credential at
  all): prefer a small rewording of the code over an ignore entry; use
  `ignored_matches` in `.gitguardian.yaml` only as a last resort, with a comment.
