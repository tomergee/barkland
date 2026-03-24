#!/bin/bash
# Exit immediately if a command exits with a non-zero status
set -e

# Configuration
if [ -f "./.configuration" ]; then
    source "./.configuration"
else
    echo "Error: .configuration file not found. Please create one based on the README."
    exit 1
fi

for var in PROJECT_ID LOCATION CLUSTER_NAME NAMESPACE REPO; do
    if [ -z "${!var}" ]; then
        echo "Error: Required configuration field $var is not set in .configuration"
        exit 1
    fi
done

if [ ! -d "../agent-sandbox" ]; then
    echo "=== [0/5] Cloning agent-sandbox from upstream ==="
    git clone https://github.com/kubernetes-sigs/agent-sandbox ../agent-sandbox
fi

echo "=== [1/5] Acquiring GKE cluster credentials ==="
gcloud container clusters get-credentials ${CLUSTER_NAME} --region ${LOCATION} --project ${PROJECT_ID}

echo "=== [2/5] Creating Namespace: ${NAMESPACE} ==="
kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

echo "=== [2a/5] Creating/Updating Gemini API Key Secret ==="
if [ -z "$GEMINI_API_KEY" ]; then
    echo "Warning: GEMINI_API_KEY is not set in environment."
else
    kubectl create secret generic gemini-api-key --from-literal=GEMINI_API_KEY="${GEMINI_API_KEY}" -n ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -
fi

echo "=== [2b/5] Deploying agent-sandbox Prerequisite ==="
# Build and Push Controller Image
(cd ../agent-sandbox && ./dev/tools/push-images --image-prefix=${LOCATION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/ --controller-only)

# Deploy Controller to Kube
(cd ../agent-sandbox && ./dev/tools/deploy-to-kube --image-prefix=${LOCATION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/)

echo "Enabling extensions mode on agent-sandbox-controller..."
kubectl patch deployment agent-sandbox-controller \
    -n agent-sandbox-system \
    -p '{"spec": {"template": {"spec": {"containers": [{"name": "agent-sandbox-controller", "args": ["--leader-elect=true", "--extensions=true"]}]}}}}'

echo "=== [3/5] Building and Pushing Barkland Images ==="
if [ ! -f "Dockerfile" ]; then
    echo "Error: deploy.sh must be run from the repository root (e.g., ./scripts/deploy.sh)"
    exit 1
fi

# echo "Copying Sandbox Python SDK client..."
# cp -r ../agent-sandbox/clients/python/agentic-sandbox-client ./agentic-sandbox-client


./scripts/push-images --image-prefix=${LOCATION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/ --extra-image-tag latest

echo "=== [4/5] Applying Kubernetes Manifests ==="
kubectl apply -f k8s/
kubectl rollout restart deployment/barkland-orchestrator -n barkland


echo "=== [5/5] Verifying Deployment Status ==="
kubectl rollout status deployment/barkland-orchestrator -n ${NAMESPACE}

echo "=== [6/5] Verifying SandboxWarmPool Status ==="
kubectl get sandboxwarmpools -n ${NAMESPACE}


echo "=== Barkland Deployment Complete! ==="
echo "You can check the external IP using:"
echo "kubectl get svc barkland-orchestrator -n ${NAMESPACE}"
