# =============================================================================
# Variables
# =============================================================================

# -----------------------------------------------------------------------------
# AWS Credentials (REQUIRED - from environment variables)
# 
# Set these before running terraform:
#   export TF_VAR_aws_access_key_id="AKIA..."
#   export TF_VAR_aws_secret_access_key="..."
#   export TF_VAR_aws_region="us-east-1"
# -----------------------------------------------------------------------------

variable "aws_access_key_id" {
  description = "AWS Access Key ID (set via TF_VAR_aws_access_key_id)"
  type        = string
  sensitive   = true
  
  validation {
    condition     = length(var.aws_access_key_id) > 0
    error_message = "AWS_ACCESS_KEY_ID is required. Set TF_VAR_aws_access_key_id environment variable."
  }
}

variable "aws_secret_access_key" {
  description = "AWS Secret Access Key (set via TF_VAR_aws_secret_access_key)"
  type        = string
  sensitive   = true
  
  validation {
    condition     = length(var.aws_secret_access_key) > 0
    error_message = "AWS_SECRET_ACCESS_KEY is required. Set TF_VAR_aws_secret_access_key environment variable."
  }
}

variable "aws_region" {
  description = "AWS region to deploy to (set via TF_VAR_aws_region)"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "memoir"
}

# -----------------------------------------------------------------------------
# App Runner
# -----------------------------------------------------------------------------

variable "app_runner_cpu" {
  description = "CPU units for App Runner (256, 512, 1024, 2048, 4096)"
  type        = string
  default     = "1024"  # 1 vCPU
}

variable "app_runner_memory" {
  description = "Memory in MB for App Runner (512, 1024, 2048, 3072, 4096, ...)"
  type        = string
  default     = "2048"  # 2 GB
}

variable "app_runner_min_instances" {
  description = "Minimum number of instances (0 = scale to zero)"
  type        = number
  default     = 1
}

variable "app_runner_max_instances" {
  description = "Maximum number of instances"
  type        = number
  default     = 5
}

variable "github_repo_url" {
  description = "GitHub repository URL"
  type        = string
  default     = ""  # Set in tfvars
}

variable "github_branch" {
  description = "GitHub branch to deploy"
  type        = string
  default     = "main"
}

# -----------------------------------------------------------------------------
# Database
# -----------------------------------------------------------------------------

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "Allocated storage in GB"
  type        = number
  default     = 20
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "memoir"
}

variable "db_username" {
  description = "Database master username"
  type        = string
  default     = "memoir_admin"
}

variable "db_multi_az" {
  description = "Enable Multi-AZ for RDS"
  type        = bool
  default     = false
}

variable "db_skip_final_snapshot" {
  description = "Skip final snapshot on deletion"
  type        = bool
  default     = true  # Set to false for production
}

# -----------------------------------------------------------------------------
# API Keys (stored in Secrets Manager)
# -----------------------------------------------------------------------------

variable "gemini_api_key" {
  description = "Google Gemini API key"
  type        = string
  sensitive   = true
  default     = ""  # Set via TF_VAR_gemini_api_key or tfvars
}

variable "openai_api_key" {
  description = "OpenAI API key (for Whisper transcription)"
  type        = string
  sensitive   = true
  default     = ""
}

# -----------------------------------------------------------------------------
# Domain (optional)
# -----------------------------------------------------------------------------

variable "domain_name" {
  description = "Custom domain name (optional)"
  type        = string
  default     = ""
}

variable "certificate_arn" {
  description = "ACM certificate ARN for custom domain"
  type        = string
  default     = ""
}

