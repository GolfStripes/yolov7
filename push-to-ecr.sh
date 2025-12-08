#!/bin/bash
set -e  # Exit on error

# -------------------------------------------------------
# Parse optional --tag argument
# -------------------------------------------------------
VERSION_TAG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag)
      VERSION_TAG="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: $0 [--tag <version>]"
      exit 1
      ;;
  esac
done

if [[ -n "$VERSION_TAG" ]]; then
  echo "🏷️ Version tag detected: $VERSION_TAG"
fi

# -------------------------------------------------------
# Download model weights (always from dev)
# -------------------------------------------------------
if [ ! -f best.pt ]; then
  echo "Weights not found, downloading from S3 (dev bucket)..."
  aws s3 cp s3://golfstripes-model-data/models/yolov7/gs-v1/best.pt .
else
  echo "File already exists, skipping download."
fi

# -------------------------------------------------------
# Define repo + local tags
# -------------------------------------------------------
ECR_BASE="842676010442.dkr.ecr.us-east-1.amazonaws.com/golfstripes-yolov7"
LOCAL_LATEST="golfstripes-yolov7:latest"
LOCAL_VERSIONED=""

if [[ -n "$VERSION_TAG" ]]; then
  LOCAL_VERSIONED="golfstripes-yolov7:${VERSION_TAG}"
fi

# -------------------------------------------------------
# Build image
# -------------------------------------------------------
echo "🔧 Building Docker image..."
docker buildx build --platform linux/amd64 -t $LOCAL_LATEST .

# Tag versioned locally if needed
if [[ -n "$LOCAL_VERSIONED" ]]; then
  docker tag $LOCAL_LATEST $LOCAL_VERSIONED
fi

# -------------------------------------------------------
# Authenticate to ECR
# -------------------------------------------------------
echo "🔐 Logging in to ECR..."
aws ecr get-login-password --region us-east-1 --profile golfstripes \
  | docker login --username AWS --password-stdin 842676010442.dkr.ecr.us-east-1.amazonaws.com

# -------------------------------------------------------
# Push "latest"
# -------------------------------------------------------
echo "🚀 Pushing latest to ECR..."
docker tag $LOCAL_LATEST "${ECR_BASE}:latest"
docker push "${ECR_BASE}:latest"

# -------------------------------------------------------
# Push version tag (if provided)
# -------------------------------------------------------
if [[ -n "$VERSION_TAG" ]]; then
  echo "🚀 Pushing version tag ${VERSION_TAG}..."
  docker tag $LOCAL_VERSIONED "${ECR_BASE}:${VERSION_TAG}"
  docker push "${ECR_BASE}:${VERSION_TAG}"
fi

echo "✅ Push complete!"
if [[ -n "$VERSION_TAG" ]]; then
  echo "   → Pushed: latest and ${VERSION_TAG}"
else
  echo "   → Pushed: latest"
fi