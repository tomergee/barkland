#!/bin/bash
# Exit immediately if a command exits with a non-zero status
set -e

# Configuration
PROJECT_ID="gke-ai-eco-dev"
LOCATION="us-central1"
CLUSTER_NAME="tomer-barkland"
NAMESPACE="barkland"

if [ ! -d "../agent-sandbox" ]; then
    echo "=== [0/5] Cloning agent-sandbox from upstream ==="
    git clone https://github.com/kubernetes-sigs/agent-sandbox ../agent-sandbox
fi

echo "=== [1/5] Acquiring GKE cluster credentials ==="
gcloud container clusters get-credentials ${CLUSTER_NAME} --region ${LOCATION} --project ${PROJECT_ID}

echo "=== [2/5] Creating Namespace: ${NAMESPACE} ==="
kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

echo "=== [2b/5] Deploying agent-sandbox Prerequisite ==="
# Build and Push Controller Image
../agent-sandbox/dev/tools/push-images --image-prefix=${LOCATION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/

# Deploy Controller to Kube
../agent-sandbox/dev/tools/deploy-to-kube --image-prefix=${LOCATION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/

echo "Enabling extensions mode on agent-sandbox-controller..."
kubectl patch deployment agent-sandbox-controller \
    -n agent-sandbox-system \
    -p '{"spec": {"template": {"spec": {"containers": [{"name": "agent-sandbox-controller", "args": ["--leader-elect=true", "--extensions=true"]}]}}}}'

echo "=== [3/5] Building and Pushing Barkland Images ==="
if [ ! -f "Dockerfile" ]; then
    echo "Error: deploy.sh must be run from the repository root (e.g., ./scripts/deploy.sh)"
    exit 1
fi

echo "Copying Sandbox Python SDK client..."
cp -r ../agent-sandbox/clients/python/agentic-sandbox-client ./agentic-sandbox-client

./scripts/push-images --image-prefix=${LOCATION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/

echo "=== [4/5] Applying Kubernetes Manifests ==="
kubectl apply -f k8s/

echo "=== [5/5] Verifying Deployment Status ==="
kubectl rollout status deployment/barkland-orchestrator -n ${NAMESPACE}

echo "=== Barkland Deployment Complete! ==="
echo "You can check the external IP using:"
echo "kubectl get svc barkland-orchestrator -n ${NAMESPACE}"
