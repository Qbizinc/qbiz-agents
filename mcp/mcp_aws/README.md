# aws-readonly-mcp

A read-only [MCP](https://modelcontextprotocol.io) server for AWS. It exposes
**list / describe / get** tools for **S3**, **Redshift**, and **IAM roles &
policies**. No tool performs a mutating AWS call.

The server authenticates by **assuming a read-only IAM role** via STS. Your
local/base credentials are only used to call `sts:AssumeRole`; all AWS API
calls run under the scoped role, so the role's policy is the hard ceiling on
what the server can ever do.

## Tools

**Identity**
- `whoami` — show the assumed identity (`sts:GetCallerIdentity`).

**S3**
- `s3_list_buckets`
- `s3_get_bucket_location` (bucket)
- `s3_list_objects` (bucket, prefix?, max_keys?, continuation_token?)
- `s3_get_object_metadata` (bucket, key) — HEAD only, no content download
- `s3_get_bucket_policy` (bucket)
- `s3_get_bucket_encryption` (bucket)

**Redshift**
- `redshift_describe_clusters` (region?, max_records?)
- `redshift_describe_cluster` (cluster_identifier, region?)
- `redshift_describe_cluster_snapshots` (cluster_identifier?, region?, max_records?)
- `redshift_serverless_list_namespaces` (region?)
- `redshift_serverless_list_workgroups` (region?)

**IAM**
- `iam_list_roles` (path_prefix?, max_items?)
- `iam_get_role` (role_name) — includes trust policy
- `iam_list_role_policies` (role_name) — inline + attached
- `iam_get_role_inline_policy` (role_name, policy_name)
- `iam_list_policies` (scope?, only_attached?, max_items?)
- `iam_get_policy` (policy_arn)
- `iam_get_policy_document` (policy_arn, version_id?)

## 1. Create the read-only role in AWS

Create an IAM role with the permission policy in
[`iam/readonly-role-policy.json`](iam/readonly-role-policy.json) and a trust
policy allowing your principal to assume it (see
[`iam/trust-policy.json`](iam/trust-policy.json) — replace the account ID,
user, and external ID).

```bash
aws iam create-role \
  --role-name aws-readonly-mcp \
  --assume-role-policy-document file://iam/trust-policy.json

aws iam put-role-policy \
  --role-name aws-readonly-mcp \
  --policy-name aws-readonly-mcp-perms \
  --policy-document file://iam/readonly-role-policy.json
```

> Tighten `"Resource": "*"` to specific bucket / policy ARNs for least
> privilege where you can. `s3:GetObject` is included so `s3_get_object_metadata`
> (a HEAD request) works; scope it to the prefixes you actually need.

## 2. Install

```bash
cd aws-readonly-mcp
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

Requires Python 3.10+.

## 3. Configure

Base credentials (used only to AssumeRole) come from the standard boto3 chain —
env vars, `~/.aws/credentials`, SSO, an instance role, etc. Then set:

| Variable | Required | Description |
|---|---|---|
| `AWS_READONLY_ROLE_ARN` | yes | ARN of the role to assume. |
| `AWS_READONLY_EXTERNAL_ID` | no | External ID, if the trust policy requires one. |
| `AWS_READONLY_SESSION_NAME` | no | Role session name. Default `aws-readonly-mcp`. |
| `AWS_READONLY_REGION` | no | Default region (else `AWS_REGION` / `AWS_DEFAULT_REGION`). |
| `AWS_READONLY_DURATION` | no | Session seconds. Default `3600`. |
| `AWS_PROFILE` | no | Base profile used to source AssumeRole credentials. |

## 4. Run

```bash
export AWS_READONLY_ROLE_ARN=arn:aws:iam::123456789012:role/aws-readonly-mcp
export AWS_READONLY_EXTERNAL_ID=aws-readonly-mcp
export AWS_READONLY_REGION=us-east-1
aws-readonly-mcp        # serves over stdio
```

## 5. Connect to Claude Desktop

Add to your `claude_desktop_config.json`
(macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "aws-readonly": {
      "command": "aws-readonly-mcp",
      "env": {
        "AWS_PROFILE": "default",
        "AWS_READONLY_ROLE_ARN": "arn:aws:iam::123456789012:role/aws-readonly-mcp",
        "AWS_READONLY_EXTERNAL_ID": "aws-readonly-mcp",
        "AWS_READONLY_REGION": "us-east-1"
      }
    }
  }
}
```

If `aws-readonly-mcp` isn't on the PATH Claude Desktop sees, use the full path
to the venv binary (e.g. `/path/to/aws-readonly-mcp/.venv/bin/aws-readonly-mcp`)
or run via `python -m aws_readonly_mcp.server`.

Restart Claude Desktop, then ask it to "list my S3 buckets" or "show IAM roles".

## Notes & safety

- **Read-only by construction**: only list/describe/get APIs are called, and the
  assumed role's policy enforces this regardless of the code.
- Credentials auto-refresh before the assumed session expires.
- `whoami` is the quickest way to confirm auth is wired up correctly.
