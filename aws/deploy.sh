#!/usr/bin/env bash
# GL Intelligence Platform — AWS ECS Fargate deployment
# Region: ap-south-1
# Usage: ./aws/deploy.sh [IMAGE_TAG]

set -euo pipefail

REGION="ap-south-1"
ECR_REPO="gl-intelligence-api"
CLUSTER="gl-intelligence"
SERVICE="gl-intelligence-api"
IMAGE_TAG="${1:-latest}"

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}"

echo "=== GL Intelligence Platform — Deploy to AWS ECS ==="
echo "Region:  $REGION"
echo "Account: $ACCOUNT_ID"
echo "Image:   $ECR_URI:$IMAGE_TAG"
echo ""

# 1. Login to ECR
echo "→ Logging in to ECR..."
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# 2. Create ECR repo if it doesn't exist
aws ecr describe-repositories --repository-names "$ECR_REPO" --region "$REGION" 2>/dev/null || \
  aws ecr create-repository --repository-name "$ECR_REPO" --region "$REGION"

# 3. Build and push Docker image
echo "→ Building Docker image (linux/amd64)..."
docker build --platform linux/amd64 \
  -f docker/Dockerfile.api \
  -t "${ECR_REPO}:${IMAGE_TAG}" \
  -t "${ECR_URI}:${IMAGE_TAG}" \
  .

echo "→ Pushing to ECR..."
docker push "${ECR_URI}:${IMAGE_TAG}"

# 4. Update task definition with new image
echo "→ Registering task definition..."
TASK_DEF=$(cat aws/task-definition.json | \
  sed "s|ACCOUNT_ID|${ACCOUNT_ID}|g" | \
  jq --arg img "${ECR_URI}:${IMAGE_TAG}" \
    '.containerDefinitions[0].image = $img')

aws ecs register-task-definition \
  --region "$REGION" \
  --cli-input-json "$TASK_DEF"

# 5. Get new task definition revision
NEW_REVISION=$(aws ecs describe-task-definition \
  --task-definition gl-intelligence-api \
  --region "$REGION" \
  --query 'taskDefinition.revision' --output text)

echo "→ Task definition revision: $NEW_REVISION"

# 6. Update ECS service
echo "→ Updating ECS service..."
aws ecs update-service \
  --cluster "$CLUSTER" \
  --service "$SERVICE" \
  --task-definition "gl-intelligence-api:${NEW_REVISION}" \
  --region "$REGION" \
  --force-new-deployment

echo ""
echo "✓ Deployment initiated!"
echo "  Monitor: https://${REGION}.console.aws.amazon.com/ecs/home?region=${REGION}#/clusters/${CLUSTER}/services/${SERVICE}"
echo ""
echo "  To check status:"
echo "  aws ecs describe-services --cluster $CLUSTER --services $SERVICE --region $REGION"
