# Setup: aws-readonly-explorer

## Prerequisites

- **`qba` CLI installed** — see the repo README for `pipx install qba-agents`.
- A read-only IAM role in your AWS account for the MCP server to assume. Two ways to create it:
  1. **Terraform** (recommended): `mcp/mcp_aws/Terraform/` — copy
     `terraform.tfvars.example` to `terraform.tfvars`, set
     `trusted_principal_arns` to your own AWS identity (or a shared
     SSO/team role ARN), then `terraform init && terraform apply`.
  2. **Manual**: follow `mcp/mcp_aws/README.md`'s `aws iam create-role` /
     `put-role-policy` steps using `mcp/mcp_aws/iam/readonly-role-policy.json`
     and `mcp/mcp_aws/iam/trust-policy.json`.
- Base AWS credentials locally (env vars, `~/.aws/credentials`, SSO, or an
  instance role) that are trusted by that role's trust policy, so the MCP
  server can call `sts:AssumeRole` into it.

## Adding the MCP to your project

```bash
qba agent mcp add aws
```

You'll be prompted for:

| Variable | What to enter |
|---|---|
| `AWS_READONLY_ROLE_ARN` | The `role_arn` output from Terraform (or the ARN you created manually) |
| `AWS_READONLY_EXTERNAL_ID` | The `external_id` output from Terraform, if set |
| `AWS_READONLY_SESSION_NAME` | Leave default unless you need a specific session name for CloudTrail auditing |
| `AWS_READONLY_REGION` | Your default AWS region |
| `AWS_READONLY_DURATION` | Leave default (3600s) unless you need longer-lived sessions |
| `AWS_PROFILE` | Your local AWS CLI profile name, if you use named profiles |

## Add the skill

```bash
qba agent skills add aws-readonly-explorer
```

## Skipping the approval prompt (optional)

```json
{ "enableAllProjectMcpServers": true }
```
in your project's `.claude/settings.json` skips the once-per-session MCP approval prompt.

## Restart Required

Fully quit and reopen your Claude Code session (not just a new chat) after
running `qba agent mcp add aws` so the server connection is attempted fresh.

## Note on MFA-gated accounts

If your AWS account enforces MFA on IAM actions or on `sts:AssumeRole` itself,
static long-lived credentials won't be enough — you'll need to generate an
MFA-verified temporary session (`aws sts get-session-token --serial-number
<mfa-arn> --token-code <code>`) and use those temporary credentials (or a
profile backed by them) as the base credentials this server assumes the role
with.
