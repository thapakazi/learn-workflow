terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kestra = {
      source  = "kestra-io/kestra"
      version = "~> 0.17"
    }
  }
}

provider "aws" {
  region                      = var.aws_region
  access_key                  = var.use_localstack ? "test" : null
  secret_key                  = var.use_localstack ? "test" : null
  skip_credentials_validation = var.use_localstack
  skip_metadata_api_check     = var.use_localstack
  skip_requesting_account_id  = var.use_localstack

  dynamic "endpoints" {
    for_each = var.use_localstack ? [1] : []
    content {
      iam = var.localstack_endpoint
      sts = var.localstack_endpoint
    }
  }
}

provider "kestra" {
  url      = var.kestra_url
  username = var.kestra_username
  password = var.kestra_password
}
