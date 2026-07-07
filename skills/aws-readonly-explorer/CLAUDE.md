# Claude-specific notes for aws-readonly-explorer

- Invoke via the Skill tool. Once the `aws` MCP server is connected, its tools
  (`whoami`, `s3_*`, `redshift_*`, `iam_*`) are available directly in your tool
  list — call them directly, no wrapper needed.
- Call `whoami` once per session before relying on any other tool's output, and
  mention the account/role in your first response so the user can catch a
  wrong-account mistake early.
- Prefer parallel tool calls when gathering independent facts about the same
  resource (e.g. `s3_get_bucket_policy` and `s3_get_bucket_encryption` for the
  same bucket, or `iam_get_role` and `iam_list_role_policies` for the same role).
- `iam_get_policy_document` needs a `version_id`; omit it to get the default
  version rather than guessing a version string.
- If a tool call returns a JSON `error` field (this server returns errors as
  JSON payloads, not exceptions raised to you), read the `action` field to know
  the exact AWS IAM permission that was denied or misused, and check
  `mcp/mcp_aws/iam/readonly-role-policy.json` before assuming the role is
  missing a permission — the read-only role's action list may not cover
  something outside S3/Redshift/IAM.
- If `aws` is not connected, tell the user to run `qba agent mcp add aws` and
  fully restart their Claude Code session (not just a new chat).
