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

4.  **Sandbox Warmpools**:
    *   Pre-provisions a configurable number of Pods to eliminate cold-start latency when agents are launched.
    *   Maintained automatically to ensure real-time readiness for `SandboxClaims`.

---

## 🚀 Recent Optimizations & Features

*   **Asynchronous Orchestration**: Migrated from blocking thread pools to native `asyncio` for sandbox management and agent interactions, significantly improving concurrency and scaling capabilities.
*   **Inference Optimization**:
    *   **Reduced Latency**: Eliminated tool-based state lookups (e.g., `needs`, `smells`) to remove multi-turn LLM round-trips.
    *   **Prompt Inlining**: Inlined agent state and environment context directly into the per-call user prompt for immediate reactivity.
    *   **Token Limiting**: Constrained agent responses to `max_output_tokens=250` to reduce Time to First Token (TTFT) and cost.
*   **Vertex AI Integration**:
    *   Configurable via `.configuration` with `USE_VERTEX_AI="true"`.
    *   Automatically constructs full resource paths for models to leverage Vertex AI enterprise quotas.
    *   Works seamlessly with Workload Identity for keyless authentication.

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
    *   **Option A: Vertex AI (Recommended)**: Enable by setting `USE_VERTEX_AI="true"` in `.configuration`. Access is granted via Workload Identity. See [Workload Identity Federation Setup](#-workload-identity-federation-setup) for step-by-step instructions.
    *   **Option B: Gemini API Key**: Set `GEMINI_API_KEY` in your local environment or `.configuration`. The deployment script uses this to create a Kubernetes secret for agent capabilities.
-   **Local Tooling**:
    *   `gcloud` CLI initialized to your target project/cluster.
    *   `kubectl` authenticated.
    *   `docker` or `buildx` for building images locally.

---

## 🔐 Secret Management

Barkland uses a Kubernetes secret to securely manage the Gemini API key for the agents.

*   **Secret Name**: `gemini-api-key`
*   **Creation**: The `deploy.sh` script automatically creates or updates this secret in the target namespace if the `GEMINI_API_KEY` environment variable is set on your local machine (or in the `.configuration` file).
*   **Usage**: The `barkland-orchestrator` deployment mounts this secret as an environment variable (`GEMINI_API_KEY`), which the Python code uses to authenticate with the Gemini API.

> [!NOTE]
> If you are using Vertex AI (`USE_VERTEX_AI="true"` in `.configuration`), you do not need to manage this secret. Please refer to the [Workload Identity Federation Setup](#-workload-identity-federation-setup) for keyless authentication.

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
# 1. Create the Standard cluster with Workload Identity
gcloud container clusters create $CLUSTER_NAME \
    --location=$CLUSTER_LOCATION \
    --project=$PROJECT_ID \
    --workload-pool=${PROJECT_ID}.svc.id.goog \
    --machine-type=e2-standard-4 \
    --num-nodes=1 # Default pool for system workloads

# 2. Add a Node Pool with GKE Sandbox (gVisor) enabled for sandboxed workloads
gcloud container node-pools create gvisor-nodepool \
    --cluster=$CLUSTER_NAME \
    --location=$CLUSTER_LOCATION \
    --project=$PROJECT_ID \
    --sandbox type=gvisor \
    --machine-type=e2-standard-4 \
    --num-nodes=10
```

---

## 🔐 Workload Identity Federation Setup

If you choose to use Workload Identity (Option A) instead of an API Key, you can use Workload Identity Federation to grant your Kubernetes workloads direct access to Google Cloud APIs (like Vertex AI) without creating dedicated Google Cloud Service Accounts or annotating Kubernetes Service Accounts.

You just need to grant the required IAM roles directly to your Kubernetes Service Account (KSA) using its **Principal Identifier**.

### 1. Identify your Kubernetes Service Account

The Orchestrator uses the following KSA:
-   **Name**: `barkland-orchestrator-sa`
-   **Namespace**: `barkland` (or your configured namespace)

### 2. Grant Permissions to the KSA

Run the following command to grant the **Vertex AI User** role directly to the Orchestrator KSA:

```bash
export PROJECT_NUMBER="your-project-number" # Numerical Project ID
export NAMESPACE="barkland"

gcloud projects add-iam-policy-binding projects/$PROJECT_ID \
    --role="roles/aiplatform.user" \
    --member="principal://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$PROJECT_ID.svc.id.goog/subject/ns/$NAMESPACE/sa/barkland-orchestrator-sa" \
    --condition=None
```

> [!NOTE]
> Ensure you remove or comment out the `GEMINI_API_KEY` environment variables in `k8s/barkland-app.yaml` and `k8s/sandbox_template.yaml` to force the application to use the default Google credentials chain (Workload Identity).
>
> You can run the following `sed` commands to automatically comment out these blocks:
>
> ```bash
> # Comment out GEMINI_API_KEY in barkland-app.yaml
> sed -i '/- name: GEMINI_API_KEY/,/key: GEMINI_API_KEY/ s/^/#/' k8s/barkland-app.yaml
> 
> # Comment out GEMINI_API_KEY in sandbox_template.yaml
> sed -i '/- name: GEMINI_API_KEY/,/key: GEMINI_API_KEY/ s/^/#/' k8s/sandbox_template.yaml
> ```

---

## 🚀 Deployment Instructions

A bundled script is provided for easy automated deployments.

### 1. Configuration Setup

Before deploying, ensure you have created a `.configuration` file in the root of the repository to define your environment properties. The `deploy.sh` script requires these values.

```bash
cat <<EOF > .configuration
PROJECT_ID="your-project-id"
CLUSTER_LOCATION="us-central1"
REGISTRY_LOCATION="us-central1"
CLUSTER_NAME="your-cluster-name"
NAMESPACE="barkland"
REPO="barkland"
WARMPOOL_REPLICAS="200"
USE_LOCAL_AGENT_SANDBOX="true"
USE_VERTEX_AI="true"
VERTEX_LOCATION="us-central1"
EOF
```

If you are using a Gemini API Key rather than Vertex AI Workload Identity, you must also export it in your environment so the deployment script can create the Kubernetes secret:

```bash
export GEMINI_API_KEY="your-gemini-api-key"
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
4.  **Install agent-sandbox**: Installs the `agent-sandbox` controller and extensions from the official GitHub release (or from a local source if `USE_LOCAL_AGENT_SANDBOX="true"`).
5.  **Build & Push Images**: Executes `./scripts/push-images` to compile your containers and push to Artifact Registry.
6.  **Manifest Apply**: Employs `envsubst` to inject properties (like `WARMPOOL_REPLICAS` and `NAMESPACE`) from `.configuration` into the YAML definitions (e.g., `k8s/sandbox_warmpool.yaml` and `k8s/sandbox_template.yaml`) before overlaying them into the cluster space.
7.  **Rollout Verification**: Waits for readiness confirmations for critical containers and verifies the `SandboxWarmPool` status.

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

Check readiness:
```bash
kubectl get pods,svc -n barkland
```

Retrieve your dashboard endpoint:
```bash
# Obtain the external IP address
kubectl get svc barkland-orchestrator -n barkland
```
Visit the reported IP in your browser to interact with the dashboard directly!

---

## ⚡ Performance Tuning for High Scale

When running a high number of concurrent agents (e.g., 50+ dogs) or requiring high QPS, the default settings of the `agent-sandbox-controller` may cause delays in sandbox allocation.

It is recommended to tune the controller concurrency and API rate limits. You can apply the following patch to the `agent-sandbox-controller` deployment in the `agent-sandbox-system` namespace:

```bash
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
```

These settings increase the number of concurrent workers for each controller to 600 and raise the Kubernetes API client limits to 1000 QPS/Burst, preventing throttling during massive scale-ups.


## Building and Deploying from Local `agent-sandbox` Repo
If you are developing fixes in the `agent-sandbox` controller itself (located in the sibling directory `../agent-sandbox`), you can configure `deploy.sh` to build and install from your local source instead of fetching released manifests from GitHub.

1.  In your `.configuration` file, add:
    ```bash
    USE_LOCAL_AGENT_SANDBOX="true"
    ```
2.  Run `./scripts/deploy.sh`. The script will now:
    *   Use `./dev/tools/push-images` from the `agent-sandbox` repo to build and push a local controller image.
    *   Use `./dev/tools/deploy-to-kube` to apply local manifests from `../agent-sandbox/k8s` and patch the deployment to use your newly built image, with extensions enabled.
