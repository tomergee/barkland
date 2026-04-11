import os
import threading
import time
from k8s_agent_sandbox import SandboxClient
from kubernetes import client

# Disable SSL verification for testing
config = client.Configuration.get_default_copy()
config.verify_ssl = False
client.Configuration.set_default(config)

def make_claim(i):
    print(f"Creating claim {i}")
    router_url = os.getenv("SANDBOX_ROUTER_URL", "http://sandbox-router-svc:8080")
    from k8s_agent_sandbox.models import SandboxDirectConnectionConfig
    connection_config = SandboxDirectConnectionConfig(api_url=router_url)
    client = SandboxClient(connection_config=connection_config)
    try:
        start = time.time()
        sandbox = client.create_sandbox(template="dog-agent-template", namespace="barkland")
        print(f"Claim {i} bound to {sandbox.sandbox_id} in {time.time() - start:.2f}s")
        sandbox.terminate()
        print(f"Claim {i} deleted")
    except Exception as e:
        print(f"Claim {i} failed: {e}")

threads = []
for i in range(99):
    t = threading.Thread(target=make_claim, args=(i,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

print("All threads finished")
