# Barkland: Multi-Agent Simulation

Barkland is a multi-agent simulation framework where the simulated agents are represented as dogs. It leverages GKE (Google Kubernetes Engine) based Sandboxes for secure, isolated agent execution environments. It features a central **Orchestrator** governing the simulation loop/dashboard and dynamically spawns agent environments.

---

## 🏗️ Architecture Overview

The system consists of the following components:

1.  **Barkland Orchestrator**:
    *   A Python-based dashboard and API server (FastAPI + Websockets).
    *   Coordinates the simulation loop and maintains state in memory.
    *   Spawns agents via `SandboxClaims` on Kubernetes using defined templates.
    *   Exposed externally via a `LoadBalancer` Service for optimal UX.

2.  **Agent Sandboxes**:
    *   Each agent (e.g., Dog Agent) runs in a highly isolated Sandbox environment.
    *   Configurable via `SandboxTemplate` specifications.
    *   Utilizes the *same* base image as the Orchestrator for agent capabilities, ensuring consistency in dependencies.

3.  **Sandbox Router**:
    *   Assists in routing workspace or communication traffic for active sandboxes.
    *   Typically deployed as part of the core infrastructure.

---

## 🛠️ Technologies Used

*   **Google ADK (Agent Development Kit)**: Provides the fundamental LLM agent building blocks (like `LlmAgent` and tools) to construct the dog agents' behaviors and personalities.
*   **agent-sandbox SDK**: The core client framework used to programmatically provision, manage, and bridge communication with high-scale isolated Kubernetes sandboxes directly from the Python orchestrator.
*   **Google Kubernetes Engine (GKE)**: The underlying infrastructure providing scalability and workload orchestration.
*   **gVisor**: Ensures robust security and runtime isolation for each individual agent environment.
*   **FastAPI & WebSockets**: Powers the real-time Dashboard UI and persistent simulation loop.
*   **Gemini / Vertex AI**: The large language models powering the behavioral logic of the simulated dog agents.

---

## 📋 Prerequisites

Before deploying, ensure you have set up the following:

-   **Google Cloud Platform (GCP) Account**: Armed with a project.
-   **GKE Cluster**:
    *   Workload Identity **Enabled**.
    *   GKE Sandbox (gVisor) **Enabled** on your node pools.
-   **Pre-installed agent-sandbox Controller**:
    *   The `deploy.sh` script automatically installs the core and extensions components of `agent-sandbox` directly from the official GitHub releases.
-   **Model Authentication (Choose One)**:
    *   **Option A: Workload Identity (Vertex AI)**: The `barkland-orchestrator-sa` Kubernetes Service Account must be mapped to a Google Service Account (GSA) with sufficient `Vertex AI User` permissions.
    *   **Option B: Gemini API Key**: Set `GEMINI_API_KEY` in your local environment. The deployment script uses this to create a Kubernetes secret for agent capabilities.
-   **Local Tooling**:
    *   `gcloud` CLI initialized to your target project/cluster.
    *   `kubectl` authenticated.
    *   `docker` or `buildx` for building images locally.

---

## ☁️ Cloud Environment Setup

If you are starting from a fresh project, follow these steps to provision the required Google Cloud resources.

### 1. Create an Artifact Registry Repository

Create a Docker repository in Artifact Registry to store the built images.

```bash
export PROJECT_ID="your-project-id"
export REGISTRY_LOCATION="us-central1"
export REPO="barkland"

# Enable Artifact Registry API
gcloud services enable artifactregistry.googleapis.com --project=$PROJECT_ID

# Create the repository
gcloud artifacts repositories create $REPO \
    --repository-format=docker \
    --location=$REGISTRY_LOCATION \
    --project=$PROJECT_ID \
    --description="Barkland Docker repository"

# Configure Docker to authenticate with the registry
gcloud auth configure-docker ${REGISTRY_LOCATION}-docker.pkg.dev
```

### 2. Create a GKE Cluster

Barkland requires a GKE cluster with Workload Identity and GKE Sandbox (gVisor) support.

**For a GKE Autopilot Cluster (Recommended & Simplest):**
Autopilot has Workload Identity enabled by default and supports GKE Sandbox automatically when requested by pods.

```bash
export CLUSTER_NAME="your-cluster-name"
export CLUSTER_LOCATION="us-central1" # Regional is recommended for Autopilot

# Enable Kubernetes Engine API
gcloud services enable container.googleapis.com --project=$PROJECT_ID

# Create the Autopilot cluster
gcloud container clusters create-auto $CLUSTER_NAME \
    --location=$CLUSTER_LOCATION \
    --project=$PROJECT_ID
```

**For a GKE Standard Cluster:**
If you prefer a Standard cluster, you must explicitly enable Workload Identity and GKE Sandbox.

```bash
export CLUSTER_NAME="your-cluster-name"
export CLUSTER_LOCATION="us-central1-a" # Zonal

# Enable Kubernetes Engine API
gcloud services enable container.googleapis.com --project=$PROJECT_ID

# Create the Standard cluster
gcloud container clusters create $CLUSTER_NAME \
    --location=$CLUSTER_LOCATION \
    --project=$PROJECT_ID \
    --workload-pool=${PROJECT_ID}.svc.id.goog \
    --sandbox type=gvisor \
    --machine-type=e2-standard-4 \
    --num-nodes=3
```

---

## 🚀 Deployment Instructions

A bundled script is provided for easy automated deployments.

### 1. Configuration Setup

Before deploying, ensure you have created a `.configuration` file in the root of the repository to define your environment properties. The `deploy.sh` script requires these values.

```bash
cat <<EOF > .configuration
PROJECT_ID="your-project-id"
CLUSTER_LOCATION="us-central1-a" # e.g. Zone for the cluster
REGISTRY_LOCATION="us-central1"  # e.g. Region for the Artifact Registry
CLUSTER_NAME="your-cluster-name"
NAMESPACE="barkland"
REPO="barkland"
EOF
```

### 2. Simple Build & Apply
Run the full-cycle deployment script from your repository root:

```bash
chmod +x ./scripts/deploy.sh
./scripts/deploy.sh
```

### 🔍 What the deployment script does:
1.  **Sync Credentials**: Authenticates `kubectl` to your target GKE cluster.
2.  **Namespace**: Checks for and creates the `barkland` namespace.
3.  **Secrets Management**: Reads `$GEMINI_API_KEY` from your local environment and creates a generic Kubernetes secret (`gemini-api-key`) in the cluster.
4.  **Build & Push Images**: Executes `./scripts/push-images` to compile your containers and push to Artifact Registry.
5.  **Manifest Apply**: Overlays the definitions residing inside the `k8s/` directory into the cluster space.
6.  **Rollout Verification**: Waits for readiness confirmations for critical containers.

---

## 🛠 Manual Image Management

If you need to strictly separate your pushes, utilize:

```bash
# Build and Push Container Images independently
./scripts/push-images --image-prefix=us-central1-docker.pkg.dev/your-project-id/barkland/ --extra-image-tag latest
```

> [!NOTE]
> The image pushing script assumes an Artifact Registry route consistent with:
> `[REGISTRY_LOCATION]-docker.pkg.dev/[PROJECT_ID]/barkland`

---

## 🔬 Post-Deployment Verification

Check accurate readiness:
```bash
kubectl get pods,svc -n barkland
```

Retrieve your dashboard endpoint easily:
```bash
# Obtain the external IP address
kubectl get svc barkland-orchestrator -n barkland
```
Visit the reported IP in your browser browser to interact with the dashboard dashboard directly!
