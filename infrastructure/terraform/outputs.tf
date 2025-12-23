# =============================================================================
# Outputs
# =============================================================================

# App Runner
output "app_runner_url" {
  description = "App Runner service URL"
  value       = aws_apprunner_service.main.service_url
}

output "app_runner_arn" {
  description = "App Runner service ARN"
  value       = aws_apprunner_service.main.arn
}

# CloudFront
output "cloudfront_domain" {
  description = "CloudFront distribution domain"
  value       = aws_cloudfront_distribution.main.domain_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID"
  value       = aws_cloudfront_distribution.main.id
}

# Database
output "database_endpoint" {
  description = "RDS endpoint (internal)"
  value       = aws_db_instance.main.address
  sensitive   = true
}

output "database_secret_arn" {
  description = "ARN of database credentials in Secrets Manager"
  value       = aws_secretsmanager_secret.db_password.arn
}

# Storage
output "s3_bucket_name" {
  description = "S3 content bucket name"
  value       = aws_s3_bucket.content.id
}

output "s3_bucket_arn" {
  description = "S3 content bucket ARN"
  value       = aws_s3_bucket.content.arn
}

# ECR
output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = aws_ecr_repository.main.repository_url
}

# DynamoDB
output "dynamodb_translations_table" {
  description = "DynamoDB translations table name"
  value       = aws_dynamodb_table.translation_cache.name
}

output "dynamodb_sessions_table" {
  description = "DynamoDB sessions table name"
  value       = aws_dynamodb_table.sessions.name
}

# VPC
output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

# Secrets
output "api_keys_secret_arn" {
  description = "ARN of API keys in Secrets Manager"
  value       = aws_secretsmanager_secret.api_keys.arn
}

# Summary
output "deployment_summary" {
  description = "Deployment summary"
  value = <<-EOT
    
    ========================================
    Memoir Platform - Deployment Complete
    ========================================
    
    API URL:        ${aws_apprunner_service.main.service_url}
    CDN URL:        https://${aws_cloudfront_distribution.main.domain_name}
    ECR Repo:       ${aws_ecr_repository.main.repository_url}
    
    Environment:    ${var.environment}
    Region:         ${var.aws_region}
    
    Next Steps:
    1. Build and push Docker image:
       docker build -t ${aws_ecr_repository.main.repository_url}:latest .
       aws ecr get-login-password | docker login --username AWS --password-stdin ${aws_ecr_repository.main.repository_url}
       docker push ${aws_ecr_repository.main.repository_url}:latest
    
    2. Run database migrations:
       (connect via SSM or bastion if needed)
    
    3. Set up CI/CD in GitHub Actions
    
    ========================================
  EOT
}

