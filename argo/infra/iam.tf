# IAM Roles for AWS Privilege Escalation Workflow
# These roles are created in LocalStack for local development

locals {
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "*"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

# Developer Elevated Role - for debugging production issues
resource "aws_iam_role" "developer_elevated" {
  name               = "developer-elevated"
  assume_role_policy = local.assume_role_policy

  tags = {
    Environment = "development"
    Purpose     = "privilege-escalation"
  }
}

resource "aws_iam_role_policy" "developer_elevated" {
  name = "developer-elevated-policy"
  role = aws_iam_role.developer_elevated.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:*",
          "cloudwatch:*",
          "ec2:Describe*",
          "rds:Describe*",
          "s3:Get*",
          "s3:List*"
        ]
        Resource = "*"
      }
    ]
  })
}

# Read-Only Production Role - for viewing production resources
resource "aws_iam_role" "readonly_prod" {
  name               = "readonly-prod"
  assume_role_policy = local.assume_role_policy

  tags = {
    Environment = "production"
    Purpose     = "privilege-escalation"
  }
}

resource "aws_iam_role_policy" "readonly_prod" {
  name = "readonly-prod-policy"
  role = aws_iam_role.readonly_prod.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["*:Describe*", "*:Get*", "*:List*"]
        Resource = "*"
      }
    ]
  })
}

# Debug Access Role - for troubleshooting
resource "aws_iam_role" "debug_access" {
  name               = "debug-access"
  assume_role_policy = local.assume_role_policy

  tags = {
    Environment = "development"
    Purpose     = "privilege-escalation"
  }
}

resource "aws_iam_role_policy" "debug_access" {
  name = "debug-access-policy"
  role = aws_iam_role.debug_access.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:*",
          "xray:*",
          "cloudwatch:*"
        ]
        Resource = "*"
      }
    ]
  })
}
