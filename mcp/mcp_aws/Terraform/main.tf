###############################################################################
# Trust policy: who may assume the read-only role.
###############################################################################
data "aws_iam_policy_document" "assume_role" {
  statement {
    sid     = "AllowAssumeRole"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = var.trusted_principal_arns
    }

    dynamic "condition" {
      for_each = var.external_id == null ? [] : [var.external_id]
      content {
        test     = "StringEquals"
        variable = "sts:ExternalId"
        values   = [condition.value]
      }
    }
  }
}

###############################################################################
# Permissions policy: read-only S3, Redshift, IAM + caller identity.
###############################################################################
data "aws_iam_policy_document" "readonly" {
  statement {
    sid    = "S3ReadOnly"
    effect = "Allow"
    actions = [
      "s3:ListAllMyBuckets",
      "s3:GetBucketLocation",
      "s3:ListBucket",
      "s3:GetObject",
      "s3:GetBucketPolicy",
      "s3:GetEncryptionConfiguration",
    ]
    resources = var.s3_resource_arns
  }

  statement {
    sid    = "RedshiftReadOnly"
    effect = "Allow"
    actions = [
      "redshift:DescribeClusters",
      "redshift:DescribeClusterSnapshots",
      "redshift-serverless:ListNamespaces",
      "redshift-serverless:ListWorkgroups",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "IamReadOnly"
    effect = "Allow"
    actions = [
      "iam:ListRoles",
      "iam:GetRole",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
      "iam:GetRolePolicy",
      "iam:ListPolicies",
      "iam:GetPolicy",
      "iam:GetPolicyVersion",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "Identity"
    effect    = "Allow"
    actions   = ["sts:GetCallerIdentity"]
    resources = ["*"]
  }
}

###############################################################################
# Role + attached customer-managed policy.
###############################################################################
resource "aws_iam_role" "readonly" {
  name                 = var.role_name
  description          = "Read-only role assumed by the aws-readonly-mcp server (S3, Redshift, IAM)."
  assume_role_policy   = data.aws_iam_policy_document.assume_role.json
  max_session_duration = var.max_session_duration
  tags                 = var.tags
}

resource "aws_iam_policy" "readonly" {
  name        = "${var.role_name}-perms"
  description = "Read-only S3/Redshift/IAM permissions for the aws-readonly-mcp server."
  policy      = data.aws_iam_policy_document.readonly.json
  tags        = var.tags
}

resource "aws_iam_role_policy_attachment" "readonly" {
  role       = aws_iam_role.readonly.name
  policy_arn = aws_iam_policy.readonly.arn
}
