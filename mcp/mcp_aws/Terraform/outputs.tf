output "role_arn" {
  description = "ARN of the read-only role. Set this as AWS_READONLY_ROLE_ARN."
  value       = aws_iam_role.readonly.arn
}

output "role_name" {
  description = "Name of the read-only role."
  value       = aws_iam_role.readonly.name
}

output "policy_arn" {
  description = "ARN of the attached read-only permissions policy."
  value       = aws_iam_policy.readonly.arn
}

output "external_id" {
  description = "External ID to set as AWS_READONLY_EXTERNAL_ID (null if disabled)."
  value       = var.external_id
}
