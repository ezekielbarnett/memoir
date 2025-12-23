# =============================================================================
# RDS PostgreSQL Database
# =============================================================================

# Generate random password for RDS
resource "random_password" "db_password" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# Store password in Secrets Manager
resource "aws_secretsmanager_secret" "db_password" {
  name = "${var.app_name}/${var.environment}/db-password"
  
  tags = {
    Name = "${var.app_name}-${var.environment}-db-password"
  }
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id = aws_secretsmanager_secret.db_password.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.db_password.result
    host     = aws_db_instance.main.address
    port     = aws_db_instance.main.port
    database = var.db_name
  })
}

# DB Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "${var.app_name}-${var.environment}-db-subnet"
  subnet_ids = aws_subnet.private[*].id
  
  tags = {
    Name = "${var.app_name}-${var.environment}-db-subnet"
  }
}

# RDS Instance
resource "aws_db_instance" "main" {
  identifier = "${var.app_name}-${var.environment}-db"
  
  # Engine
  engine               = "postgres"
  engine_version       = "16.4"
  instance_class       = var.db_instance_class
  allocated_storage    = var.db_allocated_storage
  max_allocated_storage = var.db_allocated_storage * 2  # Allow autoscaling
  storage_type         = "gp3"
  storage_encrypted    = true
  
  # Database
  db_name  = var.db_name
  username = var.db_username
  password = random_password.db_password.result
  port     = 5432
  
  # Networking
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false
  multi_az               = var.db_multi_az
  
  # Backup
  backup_retention_period = var.environment == "prod" ? 7 : 1
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"
  
  # Performance
  performance_insights_enabled = var.environment == "prod"
  
  # Lifecycle
  skip_final_snapshot       = var.db_skip_final_snapshot
  final_snapshot_identifier = var.db_skip_final_snapshot ? null : "${var.app_name}-${var.environment}-final-snapshot"
  deletion_protection       = var.environment == "prod"
  
  tags = {
    Name = "${var.app_name}-${var.environment}-db"
  }
}

