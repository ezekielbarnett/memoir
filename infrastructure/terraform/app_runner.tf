# =============================================================================
# App Runner Service
# =============================================================================

# Store API keys in Secrets Manager
resource "aws_secretsmanager_secret" "api_keys" {
  name = "${var.app_name}/${var.environment}/api-keys"
  
  tags = {
    Name = "${var.app_name}-${var.environment}-api-keys"
  }
}

resource "aws_secretsmanager_secret_version" "api_keys" {
  secret_id = aws_secretsmanager_secret.api_keys.id
  secret_string = jsonencode({
    GEMINI_API_KEY = var.gemini_api_key
    OPENAI_API_KEY = var.openai_api_key
  })
}

# IAM Role for App Runner
resource "aws_iam_role" "app_runner" {
  name = "${var.app_name}-${var.environment}-app-runner-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "tasks.apprunner.amazonaws.com"
        }
      }
    ]
  })
}

# IAM Policy for App Runner
resource "aws_iam_role_policy" "app_runner" {
  name = "${var.app_name}-${var.environment}-app-runner-policy"
  role = aws_iam_role.app_runner.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # S3 Access
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.content.arn,
          "${aws_s3_bucket.content.arn}/*"
        ]
      },
      # DynamoDB Access
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.translation_cache.arn,
          aws_dynamodb_table.sessions.arn
        ]
      },
      # Secrets Manager Access
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_secretsmanager_secret.api_keys.arn,
          aws_secretsmanager_secret.db_password.arn
        ]
      }
    ]
  })
}

# App Runner Service
resource "aws_apprunner_service" "main" {
  service_name = "${var.app_name}-${var.environment}"
  
  source_configuration {
    auto_deployments_enabled = true
    
    # Using image-based deployment from ECR
    image_repository {
      image_identifier      = "${aws_ecr_repository.main.repository_url}:latest"
      image_repository_type = "ECR"
      
      image_configuration {
        port = "8000"
        
        runtime_environment_variables = {
          ENVIRONMENT           = var.environment
          AWS_REGION            = var.aws_region
          S3_BUCKET             = aws_s3_bucket.content.id
          DYNAMODB_TRANSLATIONS = aws_dynamodb_table.translation_cache.name
          DYNAMODB_SESSIONS     = aws_dynamodb_table.sessions.name
          LOG_LEVEL             = var.environment == "prod" ? "INFO" : "DEBUG"
        }
        
        runtime_environment_secrets = {
          DATABASE_URL   = aws_secretsmanager_secret.db_password.arn
          GEMINI_API_KEY = "${aws_secretsmanager_secret.api_keys.arn}:GEMINI_API_KEY::"
          OPENAI_API_KEY = "${aws_secretsmanager_secret.api_keys.arn}:OPENAI_API_KEY::"
        }
      }
    }
    
    authentication_configuration {
      access_role_arn = aws_iam_role.app_runner_ecr.arn
    }
  }
  
  instance_configuration {
    cpu               = var.app_runner_cpu
    memory            = var.app_runner_memory
    instance_role_arn = aws_iam_role.app_runner.arn
  }
  
  network_configuration {
    egress_configuration {
      egress_type       = "VPC"
      vpc_connector_arn = aws_apprunner_vpc_connector.main.arn
    }
  }
  
  auto_scaling_configuration_arn = aws_apprunner_auto_scaling_configuration_version.main.arn
  
  health_check_configuration {
    protocol            = "HTTP"
    path                = "/health"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }
  
  tags = {
    Name = "${var.app_name}-${var.environment}"
  }
}

# Auto Scaling Configuration
resource "aws_apprunner_auto_scaling_configuration_version" "main" {
  auto_scaling_configuration_name = "${var.app_name}-${var.environment}-autoscaling"
  
  max_concurrency = 100  # Requests per instance before scaling
  min_size        = var.app_runner_min_instances
  max_size        = var.app_runner_max_instances
  
  tags = {
    Name = "${var.app_name}-${var.environment}-autoscaling"
  }
}

# IAM Role for App Runner to access ECR
resource "aws_iam_role" "app_runner_ecr" {
  name = "${var.app_name}-${var.environment}-app-runner-ecr-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "build.apprunner.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "app_runner_ecr" {
  role       = aws_iam_role.app_runner_ecr.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

# ECR Repository
resource "aws_ecr_repository" "main" {
  name                 = "${var.app_name}-${var.environment}"
  image_tag_mutability = "MUTABLE"
  
  image_scanning_configuration {
    scan_on_push = true
  }
  
  tags = {
    Name = "${var.app_name}-${var.environment}"
  }
}

# ECR Lifecycle Policy
resource "aws_ecr_lifecycle_policy" "main" {
  repository = aws_ecr_repository.main.name
  
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# Custom Domain (optional)
resource "aws_apprunner_custom_domain_association" "main" {
  count = var.domain_name != "" ? 1 : 0
  
  domain_name = "api.${var.domain_name}"
  service_arn = aws_apprunner_service.main.arn
}

