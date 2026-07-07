# Terraform — aws-readonly-mcp role

Creates the read-only IAM role and permissions policy the MCP server assumes.

## Files
- `versions.tf` — Terraform / AWS provider constraints + provider config.
- `variables.tf` — inputs (principals, external ID, region, S3 scoping, tags).
- `main.tf` — trust policy, read-only permissions policy, role, attachment.
- `outputs.tf` — `role_arn`, `policy_arn`, `external_id`.
- `terraform.tfvars.example` — copy to `terraform.tfvars` and edit.

## Use

```bash
cd Terraform
cp terraform.tfvars.example terraform.tfvars   # then edit
terraform init
terraform plan
terraform apply
```

The credentials you run Terraform with need IAM write permissions
(`iam:CreateRole`, `iam:CreatePolicy`, `iam:AttachRolePolicy`, etc.) — these are
separate from, and broader than, what the resulting role grants.

After apply, wire the outputs into the server:

```bash
export AWS_READONLY_ROLE_ARN=$(terraform output -raw role_arn)
export AWS_READONLY_EXTERNAL_ID=$(terraform output -raw external_id)
```

## Notes
- `trusted_principal_arns` is the identity the MCP server authenticates as
  *before* assuming this role — i.e. the base credentials in its boto3 chain.
- Set `external_id = null` to drop the ExternalId condition (also unset
  `AWS_READONLY_EXTERNAL_ID`).
- Default `s3_resource_arns = ["*"]`; restrict to specific bucket ARNs
  (and `.../*` for objects) for least privilege.
