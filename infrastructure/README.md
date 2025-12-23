# Memoir Infrastructure

AWS infrastructure for the Memoir platform using Terraform.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CloudFront CDN                          │
│                    (caching, SSL termination)                   │
└─────────────────────────────┬───────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
    ┌─────────┐        ┌───────────┐        ┌───────────┐
    │   S3    │        │    App    │        │   S3      │
    │ Static  │        │  Runner   │        │  Public   │
    │ Assets  │        │   API     │        │  Content  │
    └─────────┘        └─────┬─────┘        └───────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │    RDS   │  │ DynamoDB │  │ Secrets  │
        │ Postgres │  │  Cache   │  │ Manager  │
        └──────────┘  └──────────┘  └──────────┘
```

## Quick Start

### Prerequisites

1. [Terraform](https://terraform.io) >= 1.0
2. AWS IAM credentials (Access Key ID + Secret)
3. Docker for building images

### Deploy Development Environment

```bash
cd infrastructure/terraform

# Initialize Terraform
terraform init

# Option A: Use the setup script (interactive)
source ./setup-env.sh

# Option B: Set environment variables manually
export TF_VAR_aws_access_key_id="AKIA..."
export TF_VAR_aws_secret_access_key="your-secret-key"
export TF_VAR_aws_region="us-east-1"
export TF_VAR_gemini_api_key="your-gemini-key"   # Optional

# Preview changes (see what will be created)
terraform plan -var-file=environments/dev.tfvars

# Apply (creates all resources)
terraform apply -var-file=environments/dev.tfvars
```

### ⚠️ Important: Credentials Are NOT Stored

This setup **requires environment variables** - credentials are never stored in files.
This is intentional for security and cost control:

- You explicitly control when Terraform can access AWS
- No accidental deployments from CI/CD or other tools
- Clear audit trail of who deployed when

### Build and Push Docker Image

After Terraform creates the ECR repository:

```bash
# Get ECR login
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build image
docker build -t memoir-dev .

# Tag and push
docker tag memoir-dev:latest <ecr-repo-url>:latest
docker push <ecr-repo-url>:latest
```

The App Runner service will automatically detect the new image and deploy.

## Environments

| Environment | File | Description |
|------------|------|-------------|
| `dev` | `environments/dev.tfvars` | Development - minimal resources, ~$50/month |
| `prod` | `environments/prod.tfvars` | Production - scaled, HA, ~$150-300/month |

## Resources Created

| Resource | Purpose | Est. Cost (dev) |
|----------|---------|-----------------|
| App Runner | API hosting | $5-15/month |
| RDS Postgres (t4g.micro) | Database | ~$13/month |
| S3 | Content storage | ~$1-5/month |
| DynamoDB | Translation cache | ~$1/month (on-demand) |
| CloudFront | CDN | ~$1-5/month |
| Secrets Manager | API keys | ~$1/month |
| NAT Gateway | VPC connectivity | ~$32/month |
| **Total** | | **~$55-75/month** |

### Cost Reduction Tips

For very low traffic (< 10 users), you can:

1. Remove NAT Gateway and use VPC endpoints instead
2. Set `app_runner_min_instances = 0` (cold starts ~2-5s)
3. Use `db.t4g.micro` (smallest RDS instance)

## Cost Management

### Set Up AWS Budget Alerts

Before deploying, set up a budget alert:

```bash
# Create a $50/month budget with email alerts at 80% and 100%
aws budgets create-budget \
  --account-id $(aws sts get-caller-identity --query Account --output text) \
  --budget '{
    "BudgetName": "memoir-monthly",
    "BudgetLimit": {"Amount": "50", "Unit": "USD"},
    "TimeUnit": "MONTHLY",
    "BudgetType": "COST"
  }' \
  --notifications-with-subscribers '[
    {
      "Notification": {
        "NotificationType": "ACTUAL",
        "ComparisonOperator": "GREATER_THAN",
        "Threshold": 80,
        "ThresholdType": "PERCENTAGE"
      },
      "Subscribers": [{"SubscriptionType": "EMAIL", "Address": "your@email.com"}]
    }
  ]'
```

Or via AWS Console: Billing → Budgets → Create Budget

### Check Current Costs

```bash
# View current month's cost
aws ce get-cost-and-usage \
  --time-period Start=$(date -u +%Y-%m-01),End=$(date -u +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics "UnblendedCost" \
  --query 'ResultsByTime[0].Total.UnblendedCost'

# View cost by service
aws ce get-cost-and-usage \
  --time-period Start=$(date -u +%Y-%m-01),End=$(date -u +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics "UnblendedCost" \
  --group-by Type=DIMENSION,Key=SERVICE \
  --query 'ResultsByTime[0].Groups[*].[Keys[0],Metrics.UnblendedCost.Amount]' \
  --output table
```

### Destroy When Not Using

The safest way to control costs during development:

```bash
# Destroy everything (keeps state for easy re-deploy)
terraform destroy -var-file=environments/dev.tfvars

# Re-deploy later
terraform apply -var-file=environments/dev.tfvars
```

⚠️ Note: This deletes the RDS database. Set `db_skip_final_snapshot = false` if you need to preserve data.

## Configuration

### Variables

Key variables you'll want to customize:

```hcl
# App Runner sizing
app_runner_cpu           = "1024"   # 1 vCPU
app_runner_memory        = "2048"   # 2 GB
app_runner_min_instances = 1        # 0 = scale to zero
app_runner_max_instances = 5

# Database sizing
db_instance_class     = "db.t4g.micro"
db_allocated_storage  = 20  # GB

# Custom domain (optional)
domain_name     = "memoir.yourdomain.com"
certificate_arn = "arn:aws:acm:..."
```

### Secrets

API keys are passed via environment variables:

```bash
export TF_VAR_gemini_api_key="your-key"
export TF_VAR_openai_api_key="your-key"

terraform apply ...
```

Or via a `.tfvars` file (don't commit!):

```hcl
# secrets.tfvars (gitignored)
gemini_api_key = "your-key"
openai_api_key = "your-key"
```

```bash
terraform apply -var-file=environments/dev.tfvars -var-file=secrets.tfvars
```

## Operations

### View App Runner Logs

```bash
aws apprunner list-operations \
  --service-arn $(terraform output -raw app_runner_arn)
```

Or view in CloudWatch Logs console.

### Database Access

The database is in a private subnet. To connect:

1. Use AWS SSM Session Manager with an EC2 bastion
2. Use RDS Proxy (recommended for production)
3. Temporarily modify security group (dev only)

### Scaling

App Runner automatically scales based on request volume (100 concurrent requests per instance by default).

To manually adjust:

```bash
# View current scaling
aws apprunner describe-auto-scaling-configuration \
  --auto-scaling-configuration-arn $(aws apprunner describe-service \
    --service-arn $(terraform output -raw app_runner_arn) \
    --query "Service.AutoScalingConfigurationSummary.AutoScalingConfigurationArn" \
    --output text)
```

### Destroy Environment

```bash
# Dev environment
terraform destroy -var-file=environments/dev.tfvars

# Will prompt for confirmation
```

⚠️ **Warning**: This deletes all data! Set `db_skip_final_snapshot = false` in production.

## CI/CD

The `.github/workflows/deploy.yml` workflow:

1. Runs tests on all PRs
2. Builds and pushes Docker image on merge to main/develop
3. Triggers App Runner deployment
4. Runs health check

Required GitHub Secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

## Troubleshooting

### App Runner not starting

```bash
# Check service status
aws apprunner describe-service \
  --service-arn $(terraform output -raw app_runner_arn)

# View deployment logs
aws logs tail /aws/apprunner/memoir-dev/service --follow
```

### Database connection issues

1. Check security group allows App Runner → RDS
2. Verify VPC connector is attached
3. Check secrets are correctly formatted

### Cold start too slow

Set `app_runner_min_instances = 1` to keep at least one instance warm.

## File Structure

```
infrastructure/
└── terraform/
    ├── main.tf              # Provider config, backend
    ├── variables.tf         # Input variables
    ├── outputs.tf           # Output values
    ├── vpc.tf               # VPC, subnets, security groups
    ├── database.tf          # RDS PostgreSQL
    ├── storage.tf           # S3, DynamoDB
    ├── app_runner.tf        # App Runner, ECR, IAM
    ├── cdn.tf               # CloudFront distribution
    └── environments/
        ├── dev.tfvars       # Development config
        └── prod.tfvars      # Production config
```

