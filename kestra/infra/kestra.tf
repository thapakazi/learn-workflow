# Kestra Flow and Namespace Files
# Deploys the AWS privilege escalation workflow and supporting scripts

# Deploy the workflow
resource "kestra_flow" "aws_privilege" {
  namespace = "idp.aws"
  flow_id   = "aws-privilege-escalation"
  content   = file("${path.module}/../flows/aws-privilege.yml")
}

# Deploy Python module as namespace file
resource "kestra_namespace_file" "privilege_escalation" {
  namespace = "idp.aws"
  filename  = "/scripts/privilege_escalation.py"
  content   = file("${path.module}/../scripts/privilege_escalation.py")
}
