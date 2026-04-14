# Kubernetes Client Optimizations

This document summarizes the optimizations made to the `agentic-sandbox-client` library and its usage to improve stability and performance during high-scale simulations.

## 1. Watch Replaced with Polling in `k8s_helper.py`

**Problem:**
During high concurrency simulations, the Kubernetes `watch` mechanism used to monitor `SandboxClaim` and `Sandbox` resources would occasionally hang indefinitely. This caused threads in the orchestrator to block forever, preventing new sandboxes from being created and causing the UI counters to freeze. The `timeout_seconds` parameter in the watch stream was not always reliably breaking the block under high load.

**Solution:**
Replaced the `watch` based implementation in `resolve_sandbox_name` and `wait_for_sandbox_ready` with a robust polling loop using explicit `get_namespaced_custom_object` calls and a monotonic clock deadline.

**Benefits:**
- Guaranteed timeout enforcement regardless of Kubernetes API stream behavior.
- Prevents hanging threads in the orchestrator.
- Improved reliability when resolving sandbox names and waiting for them to become ready.

## 2. Increased Creation Timeout in Orchestrator

**Problem:**
The orchestrator was using a hardcoded 10-second timeout (`sandbox_ready_timeout=10`) when creating sandboxes. Under high load (e.g., 200 concurrent agents), the control plane or the `sandbox-router` could take longer than 10 seconds to fulfill the claim and make the sandbox reachable, leading to unnecessary timeouts and retries.

**Solution:**
Increased the `sandbox_ready_timeout` to 30 seconds in `barkland/main.py` when calling `client.create_sandbox`.

**Benefits:**
- Gives the system adequate time to provision sandboxes from the warm pool under load.
- Reduces failure rate of sandbox creations during initial simulation burst.
