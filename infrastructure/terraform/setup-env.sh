#!/bin/bash
# =============================================================================
# Memoir Infrastructure - Environment Setup
# =============================================================================
#
# This script helps you set up the required environment variables.
# 
# Usage:
#   source ./setup-env.sh
#
# Then run:
#   terraform init
#   terraform plan -var-file=environments/dev.tfvars
#   terraform apply -var-file=environments/dev.tfvars
#
# =============================================================================

echo "🔐 Memoir Infrastructure Setup"
echo "=============================="
echo ""

# Check if already set
if [ -n "$TF_VAR_aws_access_key_id" ]; then
    echo "✅ AWS credentials already set"
    echo "   Account: $(echo $TF_VAR_aws_access_key_id | cut -c1-8)..."
    echo ""
    read -p "Do you want to update them? (y/N) " update
    if [[ ! "$update" =~ ^[Yy]$ ]]; then
        echo "Keeping existing credentials."
        return 0 2>/dev/null || exit 0
    fi
fi

echo "Enter your AWS credentials (from IAM console):"
echo ""

# AWS Access Key ID
read -p "AWS Access Key ID (AKIA...): " aws_key_id
if [ -z "$aws_key_id" ]; then
    echo "❌ Access Key ID is required"
    return 1 2>/dev/null || exit 1
fi

# AWS Secret Access Key
read -s -p "AWS Secret Access Key: " aws_secret
echo ""
if [ -z "$aws_secret" ]; then
    echo "❌ Secret Access Key is required"
    return 1 2>/dev/null || exit 1
fi

# AWS Region
read -p "AWS Region [us-east-1]: " aws_region
aws_region=${aws_region:-us-east-1}

# Gemini API Key (optional but recommended)
echo ""
read -p "Gemini API Key (optional, press enter to skip): " gemini_key

# Export variables
export TF_VAR_aws_access_key_id="$aws_key_id"
export TF_VAR_aws_secret_access_key="$aws_secret"
export TF_VAR_aws_region="$aws_region"
export AWS_REGION="$aws_region"

if [ -n "$gemini_key" ]; then
    export TF_VAR_gemini_api_key="$gemini_key"
    echo "✅ Gemini API key set"
fi

echo ""
echo "✅ Environment configured!"
echo ""
echo "Variables set:"
echo "  TF_VAR_aws_access_key_id     = ${TF_VAR_aws_access_key_id:0:8}..."
echo "  TF_VAR_aws_secret_access_key = ****"
echo "  TF_VAR_aws_region            = $TF_VAR_aws_region"
if [ -n "$TF_VAR_gemini_api_key" ]; then
    echo "  TF_VAR_gemini_api_key        = ${TF_VAR_gemini_api_key:0:8}..."
fi
echo ""
echo "Next steps:"
echo "  terraform init"
echo "  terraform plan -var-file=environments/dev.tfvars"
echo "  terraform apply -var-file=environments/dev.tfvars"
echo ""
echo "💡 Tip: To see estimated costs before deploying:"
echo "  terraform plan -var-file=environments/dev.tfvars"
echo ""

