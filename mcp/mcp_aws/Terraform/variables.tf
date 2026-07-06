variable "region" {
  description = "AWS region for the provider."
  type        = string
  default     = "us-east-1"
}

variable "role_name" {
  description = "Name of the read-only IAM role the MCP server assumes."
  type        = string
  default     = "aws-readonly-mcp"
}

variable "trusted_principal_arns" {
  description = <<-EOT
    IAM principal ARNs allowed to assume the role (the identity whose base
    credentials the MCP server uses to call sts:AssumeRole). Example:
    ["arn:aws:iam::123456789012:user/soren"].
  EOT
  type        = list(string)
  default     = [ "arn:aws:iam::907770664110:user/soren" ]

  validation {
    condition     = length(var.trusted_principal_arns) > 0
    error_message = "Provide at least one principal ARN allowed to assume the role."
  }
}

variable "external_id" {
  description = "External ID required in the trust policy (must match AWS_READONLY_EXTERNAL_ID). Set to null to disable."
  type        = string
  default     = "aws-readonly-mcp"
}

variable "max_session_duration" {
  description = "Maximum assumed-session duration in seconds (must be >= AWS_READONLY_DURATION)."
  type        = number
  default     = 3600
}

variable "s3_resource_arns" {
  description = "S3 resources the role may read. Default '*'. Tighten to bucket ARNs and 'arn:aws:s3:::bucket/*' for least privilege."
  type        = list(string)
  default     = ["*"]
}

variable "tags" {
  description = "Tags applied to created resources."
  type        = map(string)
  default = {
    ManagedBy = "terraform"
    Project   = "aws-readonly-mcp"
  }
}
