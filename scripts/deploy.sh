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

for var in PROJECT_ID CLUSTER_LOCATION REGISTRY_LOCATION CLUSTER_NAME NAMESPACE REPO WARMPOOL_REPLICAS; do
    if [ -z "${!var}" ]; then
        echo "Error: Required configuration field $var is not set in .configuration"
        exit 1
    fi
done

echo "=== [1/6] Acquiring GKE cluster credentials ==="
gcloud container clusters get-credentials ${CLUSTER_NAME} --location ${CLUSTER_LOCATION} --project ${PROJECT_ID}

echo "=== [2/6] Creating Namespace: ${NAMESPACE} ==="
kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

echo "=== [3/6] Creating/Updating Gemini API Key Secret ==="
if [ -z "$GEMINI_API_KEY" ]; then
    echo "Warning: GEMINI_API_KEY is not set in environment."
else
    kubectl create secret generic gemini-api-key --from-literal=GEMINI_API_KEY="${GEMINI_API_KEY}" -n ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -
fi

echo "=== [4/6] Deploying agent-sandbox Prerequisite ==="
AGENT_SANDBOX_VERSION="v0.2.1"
echo "Installing Agent Sandbox ${AGENT_SANDBOX_VERSION}..."
kubectl apply -f https://github.com/kubernetes-sigs/agent-sandbox/releases/download/${AGENT_SANDBOX_VERSION}/manifest.yaml
kubectl apply -f https://github.com/kubernetes-sigs/agent-sandbox/releases/download/${AGENT_SANDBOX_VERSION}/extensions.yaml

echo "Enabling extensions mode on agent-sandbox-controller..."
kubectl patch deployment agent-sandbox-controller \
    -n agent-sandbox-system \
    -p '{"spec": {"template": {"spec": {"containers": [{"name": "agent-sandbox-controller", "args": ["--leader-elect=true", "--extensions=true"]}]}}}}'

kubectl rollout status deployment/agent-sandbox-controller -n agent-sandbox-system

echo "=== [5/6] Building and Pushing Barkland Images ==="
if [ ! -f "Dockerfile" ]; then
    echo "Error: deploy.sh must be run from the repository root (e.g., ./scripts/deploy.sh)"
    exit 1
fi

./scripts/push-images --image-prefix=${REGISTRY_LOCATION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/ --extra-image-tag latest

echo "=== [4/5] Applying Kubernetes Manifests ==="
export PROJECT_ID CLUSTER_LOCATION REGISTRY_LOCATION CLUSTER_NAME NAMESPACE REPO WARMPOOL_REPLICAS

for file in k8s/*.yaml; do
    envsubst '$PROJECT_ID $CLUSTER_LOCATION $REGISTRY_LOCATION $CLUSTER_NAME $NAMESPACE $REPO $WARMPOOL_REPLICAS' < "$file" | kubectl apply -f -
done

kubectl rollout restart deployment/barkland-orchestrator -n ${NAMESPACE}

echo "=== Verifying Deployment Status ==="
kubectl rollout status deployment/barkland-orchestrator -n ${NAMESPACE}

echo "=== Verifying SandboxWarmPool Status ==="
kubectl get sandboxwarmpools -n ${NAMESPACE}

echo "=== Barkland Deployment Complete! ==="
echo "You can check the external IP using:"
echo "kubectl get svc barkland-orchestrator -n ${NAMESPACE}"
