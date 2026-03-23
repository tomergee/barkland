#!/bin/bash
# Exit immediately if a command exits with a non-zero status
set -e

PROJECT_ID="gke-ai-eco-dev"
LOCATION="us-central1"
REPO="barkland"
IMAGE_PREFIX="${LOCATION}-docker.pkg.dev/${PROJECT_ID}/${REPO}"
IMAGE_TAG="latest"

echo "Building and Pushing Unified Barkland Image..."
docker build --push -t ${IMAGE_PREFIX}/barkland:${IMAGE_TAG} -f Dockerfile .

echo "Done."
