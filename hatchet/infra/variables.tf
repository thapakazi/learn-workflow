variable "use_localstack" {
  description = "Whether to use LocalStack for local development"
  type        = bool
  default     = true
}

variable "localstack_endpoint" {
  description = "LocalStack endpoint URL"
  type        = string
  default     = "http://localhost:4566"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "allowed_roles" {
  description = "List of role configurations for privilege escalation"
  type = list(object({
    name        = string
    description = string
    policy_arns = list(string)
  }))
  default = [
    {
      name        = "developer-elevated"
      description = "Elevated developer access for debugging"
      policy_arns = ["arn:aws:iam::aws:policy/PowerUserAccess"]
    },
    {
      name        = "readonly-prod"
      description = "Read-only access to production resources"
      policy_arns = ["arn:aws:iam::aws:policy/ReadOnlyAccess"]
    },
    {
      name        = "debug-access"
      description = "Debug access for troubleshooting"
      policy_arns = ["arn:aws:iam::aws:policy/CloudWatchLogsReadOnlyAccess"]
    }
  ]
}
