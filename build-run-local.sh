#!/usr/bin/env bash
set -euo pipefail

# -------------------------------------------------------
# Hardcoded local test config
# -------------------------------------------------------
MEDIA_ID="c8761209-09d0-435c-8627-410617ca851f"
MEDIA_API_URL="https://dev-api.golfstripes.com/disco"

AWS_PROFILE="golfstripes"
AWS_REGION="us-east-1"

IMAGE_NAME="golfstripes-yolov7"
LOCAL_TAG="${IMAGE_NAME}:local"

# -------------------------------------------------------
# Download model weights
# -------------------------------------------------------
if [ ! -f best.pt ]; then
  echo "⬇️ Weights not found, downloading from S3..."
  aws s3 cp s3://golfstripes-model-data/models/yolov7/gs-v1/best.pt . \
    --profile "${AWS_PROFILE}" \
    --region "${AWS_REGION}"
else
  echo "✅ best.pt already exists, skipping download."
fi

# -------------------------------------------------------
# Build image locally
# -------------------------------------------------------
echo "🔧 Building Docker image locally..."

docker buildx build \
  --platform linux/amd64 \
  --load \
  -t "${LOCAL_TAG}" \
  .

echo "✅ Built image: ${LOCAL_TAG}"

# -------------------------------------------------------
# Run container locally
# -------------------------------------------------------
echo "🚀 Running container locally..."

docker run --rm -it \
  --platform linux/amd64 \
  -e MEDIA_ID="${MEDIA_ID}" \
  -e MEDIA_API_URL="${MEDIA_API_URL}" \
  -e AWS_PROFILE="${AWS_PROFILE}" \
  -e AWS_REGION="${AWS_REGION}" \
  -e AWS_DEFAULT_REGION="${AWS_REGION}" \
  -v "$HOME/.aws:/root/.aws" \
  "${LOCAL_TAG}"

echo "✅ Local container run complete!"
