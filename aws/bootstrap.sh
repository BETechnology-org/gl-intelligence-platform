#!/usr/bin/env bash
# Bootstrap AWS infrastructure for GL Intelligence Platform
# Run once to create ECS cluster, ALB, security groups, etc.
# Region: ap-south-1

set -euo pipefail

REGION="ap-south-1"
CLUSTER="gl-intelligence"
VPC_CIDR="10.0.0.0/16"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "=== Bootstrapping AWS infrastructure (account: $ACCOUNT_ID, region: $REGION) ==="

# 1. Create ECS cluster
echo "→ Creating ECS cluster..."
aws ecs create-cluster \
  --cluster-name "$CLUSTER" \
  --capacity-providers FARGATE \
  --region "$REGION" 2>/dev/null || echo "  (cluster already exists)"

# 2. Create CloudWatch log group
echo "→ Creating log group..."
aws logs create-log-group \
  --log-group-name "/ecs/gl-intelligence-api" \
  --region "$REGION" 2>/dev/null || echo "  (log group already exists)"

# 3. Create Secrets Manager secrets (placeholders — fill in via console or CLI)
echo "→ Creating Secrets Manager entries (fill in values via AWS console)..."
aws secretsmanager create-secret \
  --name "gl-intelligence/anthropic-api-key" \
  --description "Anthropic API key for GL Intelligence Platform" \
  --secret-string '{"ANTHROPIC_API_KEY":"sk-ant-REPLACE_ME"}' \
  --region "$REGION" 2>/dev/null || echo "  (anthropic secret already exists)"

aws secretsmanager create-secret \
  --name "gl-intelligence/gcp-service-account" \
  --description "GCP service account JSON for BigQuery access" \
  --secret-string '{}' \
  --region "$REGION" 2>/dev/null || echo "  (gcp secret already exists)"

# 4. Create IAM execution role
echo "→ Creating ECS task execution role..."
aws iam create-role \
  --role-name "ecsTaskExecutionRole" \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]
  }' --region "$REGION" 2>/dev/null || echo "  (role already exists)"

aws iam attach-role-policy \
  --role-name "ecsTaskExecutionRole" \
  --policy-arn "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy" 2>/dev/null || true

# Allow reading secrets
aws iam put-role-policy \
  --role-name "ecsTaskExecutionRole" \
  --policy-name "ReadGLSecrets" \
  --policy-document "{
    \"Version\":\"2012-10-17\",
    \"Statement\":[{
      \"Effect\":\"Allow\",
      \"Action\":[\"secretsmanager:GetSecretValue\"],
      \"Resource\":\"arn:aws:secretsmanager:${REGION}:${ACCOUNT_ID}:secret:gl-intelligence/*\"
    }]
  }" 2>/dev/null || true

echo ""
echo "✓ Bootstrap complete!"
echo ""
echo "Next steps:"
echo "  1. Fill in secrets: aws secretsmanager update-secret --secret-id gl-intelligence/anthropic-api-key --secret-string '{\"ANTHROPIC_API_KEY\":\"sk-ant-...\"}' --region $REGION"
echo "  2. Set up VPC + ALB (or use existing VPC)"
echo "  3. Run ./aws/deploy.sh to build and deploy the container"
