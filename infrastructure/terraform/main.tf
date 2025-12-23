# =============================================================================
# Memoir Platform - AWS Infrastructure
# =============================================================================
#
# This Terraform configuration deploys:
# - App Runner for the FastAPI backend
# - RDS PostgreSQL for database
# - S3 for content storage (audio, images, exports)
# - DynamoDB for caching (translations, sessions)
# - CloudFront for CDN
# - Secrets Manager for API keys
#
# Usage:
#   cd infrastructure/terraform
#   terraform init
#   terraform plan -var-file=environments/dev.tfvars
#   terraform apply -var-file=environments/dev.tfvars
#
# =============================================================================

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  # Uncomment for remote state (recommended for production)
  # backend "s3" {
  #   bucket         = "memoir-terraform-state"
  #   key            = "terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "memoir-terraform-locks"
  # }
}

provider "aws" {
  region = var.aws_region
  
  # EXPLICIT: Only use environment variables for credentials
  # Set these before running terraform:
  #   export AWS_ACCESS_KEY_ID="AKIA..."
  #   export AWS_SECRET_ACCESS_KEY="..."
  #   export AWS_REGION="us-east-1"
  #
  # This prevents accidentally using credentials from ~/.aws/credentials
  skip_credentials_validation = false
  skip_metadata_api_check     = true   # Don't check EC2 metadata service
  skip_requesting_account_id  = false
  
  # These will cause clear errors if env vars aren't set
  access_key = var.aws_access_key_id
  secret_key = var.aws_secret_access_key
  
  default_tags {
    tags = {
      Project     = "memoir"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

