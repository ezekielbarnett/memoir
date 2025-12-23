# =============================================================================
# Development Environment Configuration
# =============================================================================

environment = "dev"
aws_region  = "us-east-1"

# -----------------------------------------------------------------------------
# App Runner (minimal for dev)
# -----------------------------------------------------------------------------
app_runner_cpu           = "1024"   # 1 vCPU
app_runner_memory        = "2048"   # 2 GB
app_runner_min_instances = 1        # Keep 1 running for fast response
app_runner_max_instances = 2

# -----------------------------------------------------------------------------
# Database (minimal for dev)
# -----------------------------------------------------------------------------
db_instance_class      = "db.t4g.micro"  # ~$13/month
db_allocated_storage   = 20              # 20 GB
db_multi_az            = false
db_skip_final_snapshot = true

# -----------------------------------------------------------------------------
# API Keys
# Set via environment variables:
#   export TF_VAR_gemini_api_key="your-key"
#   export TF_VAR_openai_api_key="your-key"
# Or pass on command line:
#   terraform apply -var="gemini_api_key=your-key"
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Domain (optional - leave empty for dev)
# -----------------------------------------------------------------------------
domain_name     = ""
certificate_arn = ""

