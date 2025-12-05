output "role_arns" {
  description = "ARNs of the created IAM roles"
  value = {
    for name, role in aws_iam_role.escalation_roles : name => role.arn
  }
}

output "role_names" {
  description = "Names of the created IAM roles"
  value       = [for role in aws_iam_role.escalation_roles : role.name]
}

output "example_workflow_input" {
  description = "Example input for triggering the AWS privilege escalation workflow"
  value = {
    user_email     = "developer@example.com"
    role_arn       = aws_iam_role.escalation_roles["developer-elevated"].arn
    duration_hours = 2
    justification  = "Need elevated access for debugging production issue"
    approver_email = "manager@example.com"
  }
}
