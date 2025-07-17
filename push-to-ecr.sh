#!/bin/bash
set -e  # Exit on error

# download the model weights
if [ ! -f best.pt ]; then
  echo "Weights not found, downloading from S3..."
  aws s3 cp s3://dev-golfstripes-model-data/models/yolov7/gs-v1/best.pt .
else
  echo "File already exists, skipping download."
fi

# Define image names
LOCAL_TAG="gs-yolov7:latest"
ECR_REPO="842676010442.dkr.ecr.us-east-1.amazonaws.com/gs-yolov7:latest"

# Build the image for ECS Fargate (linux/amd64) and tag locally
echo "🔧 Building Docker image..."
docker buildx build --platform linux/amd64 -t $LOCAL_TAG .
#docker build -t $LOCAL_TAG .

# Tag it for ECR
echo "🏷️ Tagging image for ECR..."
docker tag $LOCAL_TAG $ECR_REPO

# Authenticate to ECR
echo "🔐 Logging in to ECR..."
aws ecr get-login-password --region us-east-1 --profile golfstripes \
  | docker login --username AWS --password-stdin 842676010442.dkr.ecr.us-east-1.amazonaws.com

# Push to ECR
echo "🚀 Pushing image to ECR..."
docker push $ECR_REPO

echo "✅ Done! Image pushed to $ECR_REPO"
