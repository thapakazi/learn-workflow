output "developer_elevated_role_arn" {
  description = "ARN of the developer-elevated role"
  value       = aws_iam_role.developer_elevated.arn
}

output "readonly_prod_role_arn" {
  description = "ARN of the readonly-prod role"
  value       = aws_iam_role.readonly_prod.arn
}

output "debug_access_role_arn" {
  description = "ARN of the debug-access role"
  value       = aws_iam_role.debug_access.arn
}
