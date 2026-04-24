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
if [ "${USE_LOCAL_AGENT_SANDBOX}" = "true" ]; then
    echo "Building and installing Agent Sandbox from local repo using its tools..."
    IMAGE_TAG="local-$(date +%s)"
    IMAGE_PREFIX="${REGISTRY_LOCATION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/"
    
    # Build and push
    (cd ../agent-sandbox && ./dev/tools/push-images --image-prefix ${IMAGE_PREFIX} --controller-only --image-tag ${IMAGE_TAG})
    
    # Deploy
    CONTROLLER_ARGS="--leader-elect=true --extensions=true --sandbox-concurrent-workers=600 --sandbox-claim-concurrent-workers=600 --sandbox-warm-pool-concurrent-workers=600 --kube-api-qps=1000 --kube-api-burst=1000"
    (cd ../agent-sandbox && ./dev/tools/deploy-to-kube --image-prefix ${IMAGE_PREFIX} --extensions --image-tag ${IMAGE_TAG} --controller-args "${CONTROLLER_ARGS}")
else
    AGENT_SANDBOX_VERSION="v0.2.1"
    echo "Installing Agent Sandbox ${AGENT_SANDBOX_VERSION}..."
    kubectl apply -f https://github.com/kubernetes-sigs/agent-sandbox/releases/download/${AGENT_SANDBOX_VERSION}/manifest.yaml
    kubectl apply -f https://github.com/kubernetes-sigs/agent-sandbox/releases/download/${AGENT_SANDBOX_VERSION}/extensions.yaml
fi

echo "Enabling extensions mode and setting high concurrency on agent-sandbox-controller..."
kubectl patch deployment agent-sandbox-controller -n agent-sandbox-system --type='json' -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/args", "value": [
    "--leader-elect=true",
    "--extensions=true",
    "--sandbox-concurrent-workers=600",
    "--sandbox-claim-concurrent-workers=600",
    "--sandbox-warm-pool-concurrent-workers=600",
    "--kube-api-qps=1000",
    "--kube-api-burst=1000"
  ]}
]'

kubectl rollout status deployment/agent-sandbox-controller -n agent-sandbox-system

echo "=== [5/6] Building and Pushing Barkland Images ==="
if [ ! -f "Dockerfile" ]; then
    echo "Error: deploy.sh must be run from the repository root (e.g., ./scripts/deploy.sh)"
    exit 1
fi

./scripts/push-images --image-prefix=${REGISTRY_LOCATION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/ --extra-image-tag latest

echo "=== [6/6] Applying Kubernetes Manifests ==="
# Provide defaults for simulation variables if not set
export SPEED_MS=${SPEED_MS:-1000}
export SPEAK_BATCH_SIZE=${SPEAK_BATCH_SIZE:-50}

export PROJECT_ID CLUSTER_LOCATION REGISTRY_LOCATION CLUSTER_NAME NAMESPACE REPO WARMPOOL_REPLICAS

for file in k8s/*.yaml; do
    envsubst '$PROJECT_ID $CLUSTER_LOCATION $REGISTRY_LOCATION $CLUSTER_NAME $NAMESPACE $REPO $WARMPOOL_REPLICAS $SPEED_MS $SPEAK_BATCH_SIZE' < "$file" | kubectl apply -f -
done

echo "Ensuring sandbox-router has 4 replicas for high capacity..."
kubectl scale deployment sandbox-router-deployment --replicas=4 -n ${NAMESPACE}

kubectl rollout restart deployment/barkland-orchestrator -n ${NAMESPACE}

echo "=== Verifying Deployment Status ==="
kubectl rollout status deployment/barkland-orchestrator -n ${NAMESPACE}

echo "=== Verifying SandboxWarmPool Status ==="
kubectl get sandboxwarmpools -n ${NAMESPACE}

echo "=== Barkland Deployment Complete! ==="
echo "You can check the external IP using:"
echo "kubectl get svc barkland-orchestrator -n ${NAMESPACE}"
