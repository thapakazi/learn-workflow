variable "localstack_endpoint" {
  description = "LocalStack endpoint URL (port-forwarded from K8s)"
  type        = string
  default     = "http://localhost:4566"
}
