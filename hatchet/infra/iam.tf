# Trust policy allowing STS AssumeRole
data "aws_iam_policy_document" "assume_role_policy" {
  statement {
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }
    actions = ["sts:AssumeRole"]
  }
}

# Create IAM roles for privilege escalation
resource "aws_iam_role" "escalation_roles" {
  for_each = { for role in var.allowed_roles : role.name => role }

  name               = each.value.name
  description        = each.value.description
  assume_role_policy = data.aws_iam_policy_document.assume_role_policy.json

  tags = {
    Purpose   = "IDP-PrivilegeEscalation"
    ManagedBy = "OpenTofu"
  }
}

# Attach policies to roles
resource "aws_iam_role_policy_attachment" "escalation_policies" {
  for_each = {
    for pair in flatten([
      for role in var.allowed_roles : [
        for policy_arn in role.policy_arns : {
          key        = "${role.name}-${replace(policy_arn, "/", "-")}"
          role_name  = role.name
          policy_arn = policy_arn
        }
      ]
    ]) : pair.key => pair
  }

  role       = aws_iam_role.escalation_roles[each.value.role_name].name
  policy_arn = each.value.policy_arn
}
