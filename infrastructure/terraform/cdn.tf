# =============================================================================
# CloudFront CDN
# =============================================================================

# Origin Access Identity for S3
resource "aws_cloudfront_origin_access_identity" "main" {
  comment = "${var.app_name}-${var.environment}-oai"
}

# S3 bucket policy for CloudFront
resource "aws_s3_bucket_policy" "content" {
  bucket = aws_s3_bucket.content.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontRead"
        Effect = "Allow"
        Principal = {
          AWS = aws_cloudfront_origin_access_identity.main.iam_arn
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.content.arn}/public/*"
      }
    ]
  })
}

# CloudFront Distribution
resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "${var.app_name}-${var.environment}"
  default_root_object = "index.html"
  price_class         = var.environment == "prod" ? "PriceClass_All" : "PriceClass_100"
  
  # Custom domain
  aliases = var.domain_name != "" ? [var.domain_name, "www.${var.domain_name}"] : []
  
  # S3 Origin (for static assets and public content)
  origin {
    domain_name = aws_s3_bucket.content.bucket_regional_domain_name
    origin_id   = "S3-content"
    origin_path = "/public"
    
    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.main.cloudfront_access_identity_path
    }
  }
  
  # App Runner Origin (for API)
  origin {
    domain_name = replace(aws_apprunner_service.main.service_url, "https://", "")
    origin_id   = "AppRunner-API"
    
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }
  
  # Default behavior (S3 static content)
  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-content"
    
    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
    
    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
    compress               = true
  }
  
  # API behavior
  ordered_cache_behavior {
    path_pattern     = "/api/*"
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "AppRunner-API"
    
    forwarded_values {
      query_string = true
      headers      = ["Authorization", "Accept", "Accept-Language", "Content-Type"]
      cookies {
        forward = "all"
      }
    }
    
    viewer_protocol_policy = "https-only"
    min_ttl                = 0
    default_ttl            = 0  # Don't cache API responses
    max_ttl                = 0
    compress               = true
  }
  
  # Health check (no caching)
  ordered_cache_behavior {
    path_pattern     = "/health"
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "AppRunner-API"
    
    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
    
    viewer_protocol_policy = "https-only"
    min_ttl                = 0
    default_ttl            = 0
    max_ttl                = 0
  }
  
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
  
  viewer_certificate {
    cloudfront_default_certificate = var.certificate_arn == ""
    acm_certificate_arn            = var.certificate_arn != "" ? var.certificate_arn : null
    ssl_support_method             = var.certificate_arn != "" ? "sni-only" : null
    minimum_protocol_version       = "TLSv1.2_2021"
  }
  
  tags = {
    Name = "${var.app_name}-${var.environment}-cdn"
  }
}

