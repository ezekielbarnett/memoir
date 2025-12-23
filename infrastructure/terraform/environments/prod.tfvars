# =============================================================================
# Production Environment Configuration
# =============================================================================

environment = "prod"
aws_region  = "us-east-1"

# -----------------------------------------------------------------------------
# App Runner (scaled for production)
# -----------------------------------------------------------------------------
app_runner_cpu           = "2048"   # 2 vCPU
app_runner_memory        = "4096"   # 4 GB
app_runner_min_instances = 2        # Always 2 for availability
app_runner_max_instances = 10       # Scale up to 10 for bursts

# -----------------------------------------------------------------------------
# Database (production-ready)
# -----------------------------------------------------------------------------
db_instance_class      = "db.t4g.small"  # ~$26/month
db_allocated_storage   = 50              # 50 GB with autoscaling
db_multi_az            = true            # High availability
db_skip_final_snapshot = false           # Keep final snapshot

# -----------------------------------------------------------------------------
# Domain
# -----------------------------------------------------------------------------
domain_name     = "memoir.yourdomain.com"  # Update this!
certificate_arn = ""                        # ACM certificate ARN

# -----------------------------------------------------------------------------
# API Keys
# Set via environment variables or AWS Secrets Manager:
#   export TF_VAR_gemini_api_key="your-key"
#   export TF_VAR_openai_api_key="your-key"
# -----------------------------------------------------------------------------

