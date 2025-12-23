# =============================================================================
# S3 Storage
# =============================================================================

# Main content bucket (audio, images, exports)
resource "aws_s3_bucket" "content" {
  bucket = "${var.app_name}-${var.environment}-content-${data.aws_caller_identity.current.account_id}"
  
  tags = {
    Name = "${var.app_name}-${var.environment}-content"
  }
}

resource "aws_s3_bucket_versioning" "content" {
  bucket = aws_s3_bucket.content.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "content" {
  bucket = aws_s3_bucket.content.id
  
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "content" {
  bucket = aws_s3_bucket.content.id
  
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "content" {
  bucket = aws_s3_bucket.content.id
  
  # Move old audio to cheaper storage
  rule {
    id     = "archive-audio"
    status = "Enabled"
    
    filter {
      prefix = "audio/"
    }
    
    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
    
    transition {
      days          = 365
      storage_class = "GLACIER"
    }
  }
  
  # Clean up temporary uploads
  rule {
    id     = "cleanup-temp"
    status = "Enabled"
    
    filter {
      prefix = "temp/"
    }
    
    expiration {
      days = 7
    }
  }
}

# CORS for frontend uploads
resource "aws_s3_bucket_cors_configuration" "content" {
  bucket = aws_s3_bucket.content.id
  
  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST"]
    allowed_origins = var.environment == "prod" ? ["https://${var.domain_name}"] : ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3600
  }
}

# =============================================================================
# DynamoDB Tables (for caching)
# =============================================================================

# Translation cache
resource "aws_dynamodb_table" "translation_cache" {
  name         = "${var.app_name}-${var.environment}-translations"
  billing_mode = "PAY_PER_REQUEST"  # No capacity planning needed
  hash_key     = "cache_key"
  
  attribute {
    name = "cache_key"
    type = "S"
  }
  
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }
  
  tags = {
    Name = "${var.app_name}-${var.environment}-translations"
  }
}

# Session store (for auth tokens, rate limiting)
resource "aws_dynamodb_table" "sessions" {
  name         = "${var.app_name}-${var.environment}-sessions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"
  
  attribute {
    name = "session_id"
    type = "S"
  }
  
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }
  
  tags = {
    Name = "${var.app_name}-${var.environment}-sessions"
  }
}

