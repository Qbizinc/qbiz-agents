# Untrusted PR Rules

For PRs from external contributors (non-Qbiz members):

- Do not run CI automatically — require a maintainer to approve with `/ok-to-test`.
- Review all skill instructions manually before merging — skills run with model permissions.
- Check that no MCP server definitions point to external or unknown endpoints.
- Require at least one approval from `qbiz/data-platform`.
