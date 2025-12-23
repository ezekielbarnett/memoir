# Deploying Memoir

This guide covers everything you need to deploy Memoir to AWS.

## Overview

```
Local Development          →    AWS Production
─────────────────               ──────────────
Python + uvicorn               App Runner (auto-scaling API)
SQLite / In-memory             RDS PostgreSQL
Local files                    S3 (content storage)
                               DynamoDB (caching)
                               CloudFront (CDN)
```

**Estimated costs:**
- Development: ~$50-75/month
- Production: ~$150-300/month
- Can be destroyed when not in use to save money

---

## Step 1: Local Development (No AWS Needed)

Run locally first to make sure everything works:

```bash
# Install dependencies
uv sync

# Set your Gemini API key
export GEMINI_API_KEY="your-key"

# Run the API
.venv/bin/uvicorn memoir.api.app:app --reload

# Test it
curl http://localhost:8000/health
```

---

## Step 2: Get AWS Credentials

You need an AWS account and IAM credentials.

### 2.1 Create an AWS Account (if needed)

1. Go to https://aws.amazon.com
2. Click "Create an AWS Account"
3. Follow the steps (requires credit card)

### 2.2 Create an IAM User

Don't use your root account. Create a dedicated IAM user:

1. Go to AWS Console → IAM → Users
2. Click "Create user"
3. Name: `memoir-deploy`
4. Click "Next"
5. Select "Attach policies directly"
6. Search and check these policies:
   - `AdministratorAccess` (for initial setup)
   - Or for more restricted access, use these:
     - `AmazonEC2FullAccess`
     - `AmazonRDSFullAccess`
     - `AmazonS3FullAccess`
     - `AmazonDynamoDBFullAccess`
     - `AWSAppRunnerFullAccess`
     - `CloudFrontFullAccess`
     - `SecretsManagerReadWrite`
     - `IAMFullAccess`
7. Click "Create user"

### 2.3 Get Access Keys

1. Click on your new user
2. Go to "Security credentials" tab
3. Click "Create access key"
4. Select "Command Line Interface (CLI)"
5. Check the confirmation box, click "Next"
6. Click "Create access key"
7. **SAVE BOTH VALUES** (you only see the secret once):
   - Access key ID: `AKIA...`
   - Secret access key: `...`

---

## Step 3: Set Up Budget Alerts

**Do this before deploying!** Protect yourself from surprise bills.

### Via AWS Console (Easiest)

1. Go to AWS Console → Billing → Budgets
2. Click "Create budget"
3. Choose "Cost budget"
4. Set:
   - Budget name: `memoir-monthly`
   - Budget amount: `50` (or your limit)
   - Email: your email
5. Add alert at 80% threshold
6. Create budget

### Via CLI

```bash
# First, set your credentials temporarily
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_REGION="us-east-1"

# Create budget (replace your@email.com)
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

---

## Step 4: Install Terraform

Terraform creates all AWS resources from code.

### macOS

```bash
brew install terraform
```

### Linux

```bash
# Download
curl -O https://releases.hashicorp.com/terraform/1.7.0/terraform_1.7.0_linux_amd64.zip
unzip terraform_1.7.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/
```

### Verify

```bash
terraform --version
# Should show: Terraform v1.7.x
```

---

## Step 5: Deploy Infrastructure

### 5.1 Set Credentials

```bash
cd infrastructure/terraform

# Option A: Interactive setup
source ./setup-env.sh

# Option B: Manual
export TF_VAR_aws_access_key_id="AKIA..."
export TF_VAR_aws_secret_access_key="your-secret"
export TF_VAR_aws_region="us-east-1"
export TF_VAR_gemini_api_key="your-gemini-key"
```

**Important:** These are only set for your current terminal session. You'll need to set them again if you open a new terminal.

### 5.2 Initialize Terraform

```bash
terraform init
```

This downloads AWS provider plugins. Only needed once (or after adding new providers).

### 5.3 Preview Changes

```bash
terraform plan -var-file=environments/dev.tfvars
```

This shows exactly what will be created. Review it. Nothing is created yet.

### 5.4 Deploy

```bash
terraform apply -var-file=environments/dev.tfvars
```

Type `yes` when prompted. This takes ~5-10 minutes.

When complete, you'll see outputs like:

```
app_runner_url = "https://abc123.us-east-1.awsapprunner.com"
ecr_repository_url = "123456789.dkr.ecr.us-east-1.amazonaws.com/memoir-dev"
```

**Save these values!**

---

## Step 6: Build and Push Docker Image

The infrastructure is ready, but App Runner needs your code.

### 6.1 Install Docker

If you don't have Docker:
- macOS: https://docs.docker.com/desktop/install/mac-install/
- Linux: https://docs.docker.com/engine/install/

### 6.2 Build the Image

```bash
# From the repo root
cd /path/to/memoir

docker build -t memoir-api .
```

### 6.3 Push to ECR

```bash
# Get the ECR URL from Terraform output
ECR_URL=$(cd infrastructure/terraform && terraform output -raw ecr_repository_url)

# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin $ECR_URL

# Tag and push
docker tag memoir-api:latest $ECR_URL:latest
docker push $ECR_URL:latest
```

### 6.4 Trigger Deployment

App Runner auto-deploys when it sees a new image. Check status:

```bash
# Get service ARN
SERVICE_ARN=$(cd infrastructure/terraform && terraform output -raw app_runner_arn)

# Check status
aws apprunner describe-service --service-arn $SERVICE_ARN \
  --query 'Service.Status'
```

Wait for `RUNNING`. Then test:

```bash
APP_URL=$(cd infrastructure/terraform && terraform output -raw app_runner_url)
curl $APP_URL/health
```

---

## Step 7: Verify Everything Works

### Test the API

```bash
APP_URL=$(cd infrastructure/terraform && terraform output -raw app_runner_url)

# Health check
curl $APP_URL/health

# Create a project
curl -X POST $APP_URL/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Project", "product_id": "life_story"}'
```

### Check Logs

```bash
# View recent logs
aws logs tail /aws/apprunner/memoir-dev/service --since 1h
```

---

## Common Operations

### Check Costs

```bash
# This month's spending
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-01),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics "UnblendedCost" \
  --query 'ResultsByTime[0].Total.UnblendedCost.Amount'
```

### Update Code

After making changes:

```bash
# Rebuild and push
docker build -t memoir-api .
docker tag memoir-api:latest $ECR_URL:latest
docker push $ECR_URL:latest

# App Runner auto-deploys, or force it:
aws apprunner start-deployment --service-arn $SERVICE_ARN
```

### Change Infrastructure

Edit `.tfvars` or `.tf` files, then:

```bash
cd infrastructure/terraform
terraform plan -var-file=environments/dev.tfvars   # Preview
terraform apply -var-file=environments/dev.tfvars  # Apply
```

### Destroy Everything

To stop all AWS charges:

```bash
cd infrastructure/terraform
terraform destroy -var-file=environments/dev.tfvars
```

Type `yes` when prompted. **This deletes everything including the database.**

To preserve database data, first create a snapshot in RDS console, or set `db_skip_final_snapshot = false` in the tfvars.

### Redeploy After Destroy

```bash
cd infrastructure/terraform
terraform apply -var-file=environments/dev.tfvars

# Then rebuild and push Docker image (Step 6)
```

---

## CI/CD (Optional)

Automate deployments with GitHub Actions.

### Setup

1. Go to your GitHub repo → Settings → Secrets and variables → Actions
2. Add these secrets:
   - `AWS_ACCESS_KEY_ID` - Your access key
   - `AWS_SECRET_ACCESS_KEY` - Your secret key

3. Edit `.github/workflows/deploy.yml`:
   - Find `if: false &&` (two places)
   - Remove `false &&` from both lines

Now pushes to `main` will auto-deploy to production, and pushes to `develop` will deploy to dev.

---

## Production Checklist

Before going live:

- [ ] Set up budget alerts (Step 3)
- [ ] Use `environments/prod.tfvars` instead of `dev.tfvars`
- [ ] Set `db_skip_final_snapshot = false` (preserve data on destroy)
- [ ] Set `db_multi_az = true` (high availability)
- [ ] Configure a custom domain
- [ ] Set up CloudWatch alarms for errors
- [ ] Enable AWS CloudTrail for audit logging
- [ ] Review IAM permissions (least privilege)

---

## Troubleshooting

### "Credentials not set" error

```bash
# Check if variables are set
echo $TF_VAR_aws_access_key_id

# If empty, set them again
source ./setup-env.sh
```

### App Runner stuck in "OPERATION_IN_PROGRESS"

Wait. Deployments can take 5-10 minutes. Check:

```bash
aws apprunner describe-service --service-arn $SERVICE_ARN \
  --query 'Service.Status'
```

### Database connection errors

Check the App Runner logs:

```bash
aws logs tail /aws/apprunner/memoir-dev/service --since 1h
```

Common issues:
- VPC connector not attached
- Security group not allowing traffic
- Wrong database credentials

### "Access Denied" errors

Your IAM user may not have enough permissions. For initial setup, use `AdministratorAccess` policy, then restrict later.

### Terraform state issues

If Terraform gets confused:

```bash
# Refresh state from AWS
terraform refresh -var-file=environments/dev.tfvars

# Or import a resource manually
terraform import -var-file=environments/dev.tfvars aws_s3_bucket.content memoir-dev-content-123456789
```

---

## File Reference

```
infrastructure/
└── terraform/
    ├── main.tf              # Provider, backend config
    ├── variables.tf         # Input variables (credentials here)
    ├── outputs.tf           # Values printed after apply
    ├── vpc.tf               # Network setup
    ├── database.tf          # RDS PostgreSQL
    ├── storage.tf           # S3 + DynamoDB
    ├── app_runner.tf        # App Runner + ECR + IAM
    ├── cdn.tf               # CloudFront
    ├── setup-env.sh         # Helper to set credentials
    └── environments/
        ├── dev.tfvars       # Dev settings (~$50-75/mo)
        └── prod.tfvars      # Prod settings (~$150-300/mo)
```

---

## Optional: Email Delivery (AWS SES)

Enable transactional emails (welcome, password reset).

### Setup

1. Go to AWS Console → SES → Verified Identities
2. Click "Create identity"
3. Choose "Email address" and enter your sending email
4. Verify the email (click link in inbox)
5. Add to your `.env`:

```bash
AWS_SES_FROM_EMAIL=noreply@yourdomain.com
```

**Note:** SES starts in sandbox mode - you can only send to verified emails. Request production access when ready to launch.

---

## Optional: Google OAuth

Let users sign in with Google.

### Setup

1. Go to https://console.cloud.google.com/apis/credentials
2. Create project (if needed)
3. Click "Create Credentials" → "OAuth client ID"
4. Application type: "Web application"
5. Add authorized redirect URIs:
   - `http://localhost:3000/auth/google/callback` (dev)
   - `https://yourdomain.com/auth/google/callback` (prod)
6. Copy Client ID and Secret
7. Add to your `.env`:

```bash
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your-secret
```

### Usage

```bash
# Get authorization URL
curl http://localhost:8000/auth/google/authorize
# Returns: {"authorize_url": "https://accounts.google.com/..."}

# After user approves, exchange code for tokens
curl -X POST http://localhost:8000/auth/google/callback \
  -H "Content-Type: application/json" \
  -d '{"code": "authorization-code-from-google", "state": "..."}'
```

---

## Optional: Facebook OAuth

Let users sign in with Facebook.

### Setup

1. Go to https://developers.facebook.com/apps
2. Create app → Consumer type
3. Add "Facebook Login" product
4. Go to Settings → Basic, copy App ID and Secret
5. Add to your `.env`:

```bash
FACEBOOK_OAUTH_CLIENT_ID=your-app-id
FACEBOOK_OAUTH_CLIENT_SECRET=your-secret
```

---

## Optional: Error Tracking (Sentry)

Get notified when errors occur in production.

### Setup

1. Create account at https://sentry.io
2. Create project (Python → FastAPI)
3. Copy DSN from project settings
4. Add to your `.env`:

```bash
SENTRY_DSN=https://your-key@sentry.io/project-id
```

Sentry auto-initializes when the API starts.

---

## Environment Variables Reference

All configuration via environment variables:

```bash
# Required for AI
GEMINI_API_KEY=your-gemini-key

# Required for AWS deployment
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1

# Optional: Email
AWS_SES_FROM_EMAIL=noreply@yourdomain.com

# Optional: OAuth
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
FACEBOOK_OAUTH_CLIENT_ID=...
FACEBOOK_OAUTH_CLIENT_SECRET=...

# Optional: Error tracking
SENTRY_DSN=https://...@sentry.io/...

# JWT (auto-generated in dev, set in prod)
JWT_SECRET_KEY=your-secure-random-string
```

---

## Getting Help

- Terraform docs: https://terraform.io/docs
- AWS App Runner: https://docs.aws.amazon.com/apprunner
- Open an issue in this repo

---

**Remember:** Always destroy your infrastructure when not using it during development. You can redeploy in ~10 minutes.

