import asyncio
import time
import os
import json
import logging
from typing import List, Optional
try:
    from k8s_agent_sandbox.client import AsyncSandboxClient
except ImportError:
    AsyncSandboxClient = None
from barkland.models.dog import DogProfile
from barkland.agents.dog_agent import BarkResponse

logger = logging.getLogger(__name__)

sandbox_clients = {}
global_sandbox_client: Optional[AsyncSandboxClient] = None

def set_global_sandbox_client(client: AsyncSandboxClient):
    global global_sandbox_client
    global_sandbox_client = client

def patch_sandbox_replicas(sandbox, replicas: int):
    try:
        logger.info(f"Patching replicas to {replicas} for {sandbox.sandbox_id}...")
        start_time = time.time()
        sandbox.connector.k8s_helper.custom_objects_api.patch_namespaced_custom_object(
            group="agents.x-k8s.io",
            version="v1alpha1",
            namespace=sandbox.namespace,
            plural="sandboxes",
            name=sandbox.sandbox_id,
            body={"spec": {"replicas": replicas}}
        )
        logger.info(f"Patched replicas for {sandbox.sandbox_id} in {time.time() - start_time:.2f}s")
    except Exception as e:
        print(f"Failed to patch replicas for {sandbox.sandbox_id}: {e}")

async def create_sandbox_for_dog(dog_name: str):
    """Allocate SandboxClaim asynchronously."""
    if not global_sandbox_client:
         return
    
    max_retries = 10
    for attempt in range(max_retries):
        sandbox_clients[dog_name] = {"status": "Creating", "claim_name": f"barkland-sandbox-{dog_name.lower()}"}
        try:
             sandbox = await global_sandbox_client.create_sandbox(template="dog-agent-template", namespace="barkland", sandbox_ready_timeout=10)
             sandbox_clients[dog_name]["status"] = "Running"
             sandbox_clients[dog_name]["claim_name"] = sandbox.claim_name
             
             print(f"Waiting for sandbox {dog_name} to be reachable...")
             reach_retries = 5
             for r in range(reach_retries):
                 try:
                     res = await sandbox.commands.run("echo ready", timeout=2)
                     if res.exit_code == 0:
                         print(f"Sandbox {dog_name} is reachable!")
                         break
                 except Exception as reach_err:
                     print(f"Sandbox {dog_name} not reachable yet (attempt {r+1}/{reach_retries}): {reach_err}")
                     await asyncio.sleep(0.5)
             else:
                 print(f"Sandbox {dog_name} failed to become reachable in time.")
                 raise Exception("Sandbox not reachable")

             sandbox_clients[dog_name] = sandbox
             
             print(f"Sandbox bound for {dog_name} on attempt {attempt+1}")
             break
             
        except Exception as e:
             print(f"Attempt {attempt+1} failed creating sandbox for {dog_name}: {e}")
             if attempt == max_retries - 1:
                  print(f"Giving up on creating sandbox for {dog_name} after {max_retries} attempts.")
                  sandbox_clients.pop(dog_name, None)
             else:
                  import random
                  jitter = random.uniform(0.5, 1.2)
                  print(f"Retrying sandbox creation for {dog_name} in {jitter:.2f} seconds...")
                  await asyncio.sleep(jitter)

async def speak_and_update(a_dog, an_agent):
    try:
        logger.info(f"Calling speak for {a_dog.name}...")
        start_time = time.time()
        
        sandbox = sandbox_clients.get(a_dog.name)
        if sandbox and hasattr(sandbox, "commands") and sandbox.commands:
            use_vertex = os.getenv("USE_VERTEX_AI", "false").lower() == "true"
            project_id = os.getenv("PROJECT_ID")
            location = os.getenv("VERTEX_LOCATION", os.getenv("CLUSTER_LOCATION", "us-central1"))
            
            model_name = "gemini-2.5-flash-lite"
            if use_vertex and project_id:
                model_name = f"projects/{project_id}/locations/{location}/publishers/google/models/gemini-2.5-flash-lite"
                
            cmd = f"python -m barkland.agents.remote_speak --name '{a_dog.name}' --breed '{a_dog.breed}' --personality '{a_dog.personality.value}' --state '{a_dog.state.value}' --energy {a_dog.needs.energy} --hunger {a_dog.needs.hunger} --boredom {a_dog.needs.boredom} --model '{model_name}'"
            logger.info(f"Running command in sandbox for {a_dog.name}: {cmd}")
            exec_res = await sandbox.commands.run(cmd, timeout=2)
            if exec_res.exit_code == 0:
                try:
                    output = json.loads(exec_res.stdout)
                    if "error" in output:
                        logger.error(f"Remote speak error for {a_dog.name}: {output['error']}")
                        res = an_agent.get_mock_response()
                    else:
                        res = BarkResponse(bark=output["bark"], translation=output["translation"])
                except Exception as json_err:
                    logger.error(f"Failed to parse JSON from sandbox for {a_dog.name}: {json_err}. Raw output: {exec_res.stdout}")
                    res = an_agent.get_mock_response()
            else:
                logger.error(f"Command failed in sandbox for {a_dog.name} with exit code {exec_res.exit_code}: {exec_res.stderr}")
                res = an_agent.get_mock_response()
        else:
            logger.warning(f"No active sandbox or commands property for {a_dog.name}, falling back to local speak")
            res = await an_agent.speak()
        
        logger.info(f"Speak completed for {a_dog.name} in {time.time() - start_time:.2f}s")
        a_dog.latest_bark = f"{res.bark} <span style='font-weight: 600; color:#a855f7; display:block; margin-top:4px; font-size:0.8rem;'>({res.translation})</span>"
    except Exception as e:
        print(f"Agent speak error for {a_dog.name}: {e}")
        res = an_agent.get_mock_response()
        a_dog.latest_bark = f"{res.bark} <span style='font-weight: 600; color:#a855f7; display:block; margin-top:4px; font-size:0.8rem;'>({res.translation})</span>"
