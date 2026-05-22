#!/usr/bin/env bash
set -euo pipefail

# -------------------------------------------------------
# Hardcoded local test config
# -------------------------------------------------------
MEDIA_ID="c7df9379-73ff-4fe4-a55c-4e7d8abef7a1"
MEDIA_API_URL="https://dev-api.golfstripes.com/disco"

AWS_PROFILE="golfstripes"
AWS_REGION="us-east-1"

IMAGE_NAME="golfstripes-yolov7"
LOCAL_TAG="${IMAGE_NAME}:local"
CONTAINER_NAME="golfstripes-yolov7-local-debug"

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
# Remove old debug container if it exists
# -------------------------------------------------------
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "🧹 Removing existing container: ${CONTAINER_NAME}"
  docker rm -f "${CONTAINER_NAME}" >/dev/null
fi

# -------------------------------------------------------
# Start persistent debug container
# -------------------------------------------------------
echo "🚀 Starting persistent debug container..."

docker run -d \
  --platform linux/amd64 \
  --name "${CONTAINER_NAME}" \
  -e MEDIA_ID="${MEDIA_ID}" \
  -e MEDIA_API_URL="${MEDIA_API_URL}" \
  -e AWS_PROFILE="${AWS_PROFILE}" \
  -e AWS_REGION="${AWS_REGION}" \
  -e AWS_DEFAULT_REGION="${AWS_REGION}" \
  -v "$HOME/.aws:/root/.aws" \
  "${LOCAL_TAG}" \
  -lc "while true; do sleep 3600; done"

echo "✅ Container is running: ${CONTAINER_NAME}"
echo ""
echo "To open a shell:"
echo "  docker exec -it ${CONTAINER_NAME} bash"
echo ""
echo "To run the main script inside the container:"
echo "  docker exec -it ${CONTAINER_NAME} bash -lc 'cd /usr/src/yolov7 && python3 main.py'"
echo ""
echo "To inspect YOLO outputs after running:"
echo "  docker exec -it ${CONTAINER_NAME} bash -lc 'find /tmp/yolov7-runs -type f -maxdepth 5 -print -exec ls -lh {} \\;'"
echo ""
echo "To stop it:"
echo "  docker rm -f ${CONTAINER_NAME}"
