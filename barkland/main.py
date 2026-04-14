from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from typing import Dict, List, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import random
from pydantic import BaseModel, Field
import logging
import time
import shlex
import subprocess

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv('.configuration', override=True)
except ImportError:
    pass

is_local = os.getenv("ENVIRONMENT", "").lower() == "local"

import warnings
warnings.filterwarnings("ignore", message=".*Your application has authenticated using end user credentials.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="websockets.legacy.server")

# Seed early so module-level static declarations roll deterministically
random.seed(int(os.getenv("SEED", "42")))
from barkland.config import SimulationConfig
from barkland.engine.simulation import SimulationLoop
from barkland.models.dog import DogProfile, Personality, DogState
import threading
try:
    if is_local:
        AsyncSandboxClient = None # Force fallback out of K8s Sandbox connections
        SandboxDirectConnectionConfig = None
    else:
        from k8s_agent_sandbox import AsyncSandboxClient
        from k8s_agent_sandbox.models import SandboxDirectConnectionConfig
except ImportError:
    AsyncSandboxClient = None # Fallback for local testing without SDK
    SandboxDirectConnectionConfig = None

class ExecuteRequest(BaseModel):
    command: str

class ExecuteResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int

app = FastAPI()

@app.on_event("shutdown")
async def shutdown_event():
    if global_sandbox_client:
        await global_sandbox_client.close()

@app.post("/execute", response_model=ExecuteResponse)
async def execute_command(request: ExecuteRequest):
    try:
        args = shlex.split(request.command)
        process = subprocess.run(
            args,
            capture_output=True,
            text=True,
            cwd="/app"
        )
        return ExecuteResponse(
            stdout=process.stdout,
            stderr=process.stderr,
            exit_code=process.returncode
        )
    except Exception as e:
        return ExecuteResponse(
            stdout="",
            stderr=f"Failed to execute command: {str(e)}",
            exit_code=1
        )

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    with open("barkland/templates/dashboard.html", "r") as f:
        content = f.read()
        return HTMLResponse(content=content, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

# In-memory Simulation Instance for simplicity
config = SimulationConfig(num_ticks=500)
sim = SimulationLoop(config)

# Pre-populate some dogs with random attributes
DOG_PREFIXES = ["Sir", "Lady", "Captain", "Baron", "Count", "Professor", "Doctor", "Agent", "Chief", "Major"]
DOG_NAMES = ["Barkley", "Noodles", "Wags", "Waffles", "Biscuit", "Coco", "Peanut", "Luna", "Boots", "Daisy", "Buster", "Rex", "Stella", "Buddy"]
DOG_SUFFIXES = ["von Sniff", "the Great", "of Barkland", "III", "Jr.", "the Destroyer", "the Fast", "the Brave"]
DOG_BREEDS = ["Golden Retriever", "French Bulldog", "Beagle", "Poodle", "Husky", "Corgi", "Dachshund"]

def generate_unique_dog_names(count: int) -> List[str]:
    names_set = set()
    attempts = 0
    # Add simple numbering fallback in case we exhaust distinct combo spaces for huge counts (safety first).
    while len(names_set) < count and attempts < 1000:
        parts = []
        if random.random() < 0.4:
            parts.append(random.choice(DOG_PREFIXES))
        parts.append(random.choice(DOG_NAMES))
        if random.random() < 0.4:
            parts.append(random.choice(DOG_SUFFIXES))
        fullname = " ".join(parts)
        if fullname not in names_set:
            names_set.add(fullname)
        attempts += 1
    
    # Fallback padding if unique names didn't cover the quota
    while len(names_set) < count:
        names_set.add(f"Pup-{len(names_set) + 1}")
    return sorted(list(names_set))

# Pre-populate defaults
num_dogs = 4
unique_names = generate_unique_dog_names(num_dogs)
for name in unique_names:
    breed = random.choice(DOG_BREEDS)
    personality = random.choice(list(Personality))
    state = random.choice(list(DogState))
    sim.add_dog(DogProfile(name=name, breed=breed, personality=personality, state=state))


from barkland.agents.dog_agent import DogAgent

connected_clients: List[WebSocket] = []
sandbox_clients: Dict[str, Any] = {}
dog_agents: Dict[str, DogAgent] = {dog.name: DogAgent(dog) for dog in sim.dogs.values()}

global_sandbox_client = None
if AsyncSandboxClient:
    import os
    router_url = os.getenv("SANDBOX_ROUTER_URL", "http://sandbox-router-svc:8080")
    connection_config = SandboxDirectConnectionConfig(api_url=router_url, server_port=8000)
    global_sandbox_client = AsyncSandboxClient(connection_config=connection_config)
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
        
        import json
        sandbox = sandbox_clients.get(a_dog.name)
        if sandbox and hasattr(sandbox, "commands") and sandbox.commands:
            cmd = f"python -m barkland.agents.remote_speak --name '{a_dog.name}' --breed '{a_dog.breed}' --personality '{a_dog.personality.value}' --state '{a_dog.state.value}' --energy {a_dog.needs.energy} --hunger {a_dog.needs.hunger} --boredom {a_dog.needs.boredom}"
            logger.info(f"Running command in sandbox for {a_dog.name}: {cmd}")
            exec_res = await sandbox.commands.run(cmd, timeout=2)
            if exec_res.exit_code == 0:
                try:
                    output = json.loads(exec_res.stdout)
                    if "error" in output:
                        logger.error(f"Remote speak error for {a_dog.name}: {output['error']}")
                        res = an_agent.get_mock_response()
                    else:
                        from barkland.agents.dog_agent import BarkResponse
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


@app.get("/api/dogs")
def get_dogs():
    return [dog.__dict__ for dog in sim.dogs.values()]

class StartSimulationRequest(BaseModel):
    count: int = Field(default=4, ge=1, le=200)

@app.post("/api/simulation/start")
async def start_simulation(req: StartSimulationRequest):
    if not sim.is_running:
        # 1. Cleanup old sandbox claims fully to prevent leaks
        for dog_name in list(sandbox_clients.keys()):
            sandbox = sandbox_clients.pop(dog_name, None)
            if sandbox and not isinstance(sandbox, dict):
                asyncio.create_task(sandbox.terminate())
        
        # 2. Reset Simulation and Agent pools
        sim.dogs.clear()
        dog_agents.clear()
        sim.tick_count = 0 
        
        # 3. Generate new names layout
        names = generate_unique_dog_names(req.count)

        # 4. Run in background via asyncio task passing names list
        asyncio.create_task(run_simulation(names))
        return {"status": f"Simulation started with {req.count} dogs"}
    raise HTTPException(status_code=409, detail="Another simulation is already running right now. Please wait.")

@app.post("/api/simulation/stop")
async def stop_simulation():
    sim.is_running = False
    
    # Cleanup old sandbox claims fully to prevent leaks and race conditions
    for dog_name in list(sandbox_clients.keys()):
        sandbox = sandbox_clients.pop(dog_name, None)
        if sandbox:
            if not isinstance(sandbox, dict):
                print(f"Terminating sandbox for {dog_name} on stop...")
                asyncio.create_task(sandbox.terminate())
            else:
                claim_name = sandbox.get("claim_name")
                if claim_name and global_sandbox_client:
                    print(f"Deleting orphaned claim {claim_name} for {dog_name} on stop...")
                    asyncio.create_task(global_sandbox_client.delete_sandbox(claim_name, namespace="barkland"))
        
    return {"status": "Simulation stopped and targeted cleanup initiated"}

@app.post("/api/simulation/reset_warmpool")
async def reset_warmpool():
    if sim.is_running:
        raise HTTPException(status_code=400, detail="Cannot reset warmpool while simulation is running")
        
    try:
        # 1. Delete all claims
        subprocess.run(["kubectl", "delete", "sandboxclaims", "--all", "-n", "barkland"], check=True, capture_output=True)
        
        # 2. Delete warmpool
        subprocess.run(["kubectl", "delete", "sandboxwarmpool", "dog-agent-warmpool", "-n", "barkland", "--ignore-not-found=true"], check=True, capture_output=True)
        
        # 3. Recreate warmpool
        with open("k8s/sandbox_warmpool.yaml", "r") as f:
            template = f.read()
        
        namespace = os.getenv("NAMESPACE", "barkland")
        replicas = os.getenv("WARMPOOL_REPLICAS", "200")
        
        manifest = template.replace("${NAMESPACE}", namespace).replace("${WARMPOOL_REPLICAS}", replicas)
        
        subprocess.run(["kubectl", "apply", "-f", "-"], input=manifest.encode(), check=True, capture_output=True)
        
        # 4. Wait for replicas (up to 60 seconds)
        target = int(replicas)
        ready = "0"
        for _ in range(12): # 12 * 5 = 60 seconds
            result = subprocess.run(["kubectl", "get", "sandboxwarmpool", "dog-agent-warmpool", "-n", "barkland", "-o", "jsonpath={.status.readyReplicas}"], capture_output=True, text=True)
            ready = result.stdout.strip() or "0"
            if ready == str(target):
                return {"status": f"Warmpool reset complete. All {target} pods are ready."}
            await asyncio.sleep(5)
            
        return {"status": f"Warmpool reset initiated. Timed out waiting for full replenishment. Current ready: {ready}/{target}"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset warmpool: {e}")

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

async def run_simulation(names: List[str]):
    sim.is_running = True
    sim.start_time = time.time()
    from barkland.agents.dog_agent import DogAgent
    # generate_unique_dog_names is available globally in this file
    
    # 1. Start periodic updates while sandboxes are allocating
    async def monitor_sandboxes():
        while sim.is_running:
            await broadcast_state()
            has_pending = False
            for name in sim.dogs.keys():
                client = sandbox_clients.get(name)
                # If client is missing or still the placeholder dict, it's pending
                if not client or isinstance(client, dict):
                    has_pending = True
                    break
            # Wait, if all ready and all populated layout break setup Accuracy accurately
            if not has_pending and len(sim.dogs) == len(names):
                break
            await asyncio.sleep(1)
            
    asyncio.create_task(monitor_sandboxes())

    # 2. Populate new dogs allocation ITERATIVELY index-by-index Setup trigger Accuracy
    

    for name in names:
        if not sim.is_running:
            break
        breed = random.choice(DOG_BREEDS)
        personality = random.choice(list(Personality))
        state = random.choice(list(DogState))
        dp = DogProfile(name=name, breed=breed, personality=personality, state=state)
        
        sim.add_dog(dp)
        dog_agents[name] = DogAgent(dp)
         
        # Start Sandbox claim thread allocation layout triggers Accuracy creators layout inaccuracies
        if global_sandbox_client:
             print(f"Spawning sandbox task for {name}")
             sandbox_clients[name] = {"status": "Creating", "claim_name": f"barkland-sandbox-{name.lower()}"}
             asyncio.create_task(create_sandbox_for_dog(name))
              
        # Broadcast immediately so UI renders this card individually layout Accurate triggers payout list Accurate setups
        await broadcast_state()
        await asyncio.sleep(0.05) # 50ms stagger spacing rolling creation

    while sim.is_running and sim.tick_count < sim.config.num_ticks:
        await sim.step()
        
        for name, dog in sim.dogs.items():
            if dog.ticks_in_state == 0:
                logger.info(f"State Change: Dog {name} transitioned to {dog.state.value}")
                
            client = sandbox_clients.get(name)
            # Ensure client is a Sandbox object and not the placeholder dict
            if client and not isinstance(client, dict):
                if dog.state == DogState.SLEEPING and (time.time() - getattr(sim, "start_time", 0) >= 15):
                    if not getattr(client, "is_paused", False):
                        try:
                            client.is_paused = True # eagerly mark
                            print(f"Pausing sandbox for dog {name} in background...")
                            # Run K8s patch in background thread
                            threading.Thread(target=patch_sandbox_replicas, args=(client, 0), daemon=True).start()
                        except Exception as e:
                            print(f"Failed to initiate pause for {name}: {e}")
                else:
                    if getattr(client, "is_paused", False):
                        try:
                            client.is_paused = False # eagerly mark
                            print(f"Resuming sandbox for dog {name} in background...")
                            # Run K8s patch in background thread
                            threading.Thread(target=patch_sandbox_replicas, args=(client, 1), daemon=True).start()
                        except Exception as e:
                            print(f"Failed to initiate resume for {name}: {e}")


        if sim.tick_count > 0 and sim.tick_count % 2 == 0:
            active_dogs = list(sim.dogs.items())
            # Sort all dogs by name A-Z
            active_dogs.sort(key=lambda x: x[0])
            
            num_dogs = len(active_dogs)
            if num_dogs > 0:
                # Calculate start index based on tick count (starting at tick 2)
                cycle = (sim.tick_count - 1) // 2
                batch_size = sim.config.speak_batch_size
                start_idx = (cycle * batch_size) % num_dogs
                
                batch_size = min(batch_size, num_dogs)
                speaking_dogs = []
                for i in range(batch_size):
                    idx = (start_idx + i) % num_dogs
                    speaking_dogs.append(active_dogs[idx])
                
                for name, dog in speaking_dogs:
                    agent = dog_agents.get(name)
                    if agent:
                        asyncio.create_task(speak_and_update(dog, agent))


        # Broadcast state every 3 ticks to avoid overloading the UI
        if sim.tick_count % 3 == 0 or sim.tick_count >= sim.config.num_ticks:
            await broadcast_state()
            
        await asyncio.sleep(sim.config.speed_ms / 1000.0)
        
    sim.is_running = False
    
    # Deletion / Cleanup on stop/pause sleep cycles
    for dog_name in list(sandbox_clients.keys()):
        sandbox = sandbox_clients.pop(dog_name, None)
        if sandbox and not isinstance(sandbox, dict):
            asyncio.create_task(sandbox.terminate())
             
    await broadcast_state()

async def broadcast_state():
    # Simulate sandbox states for dashboard layout metrics
    sandboxes = []
    for i, dog in enumerate(sim.dogs.values()):
        status = "Created"
        claim_name = f"barkland-sandbox-{dog.name.lower()}"
        ip = "Allocating..."
        
        sandbox = sandbox_clients.get(dog.name)
        if sandbox:
            if isinstance(sandbox, dict):
                status = sandbox.get("status", "Creating")
                claim_name = sandbox.get("claim_name", claim_name)
            else:
                claim_name = sandbox.claim_name or claim_name
                status = "Running" if dog.state != DogState.SLEEPING else "Paused"
                ip = getattr(sandbox.connection_config, "api_url", "Dynamic IP Ready")
        else:
            # Fallback for mock view logic or triggers allocations pending
            status = "Allocating"
            if not SandboxClient:
                 status = "Running" if dog.state != DogState.SLEEPING else "Paused"
                 ip = f"10.64.{i + 1}.12"
            else:
                 # When SandboxClient is imported, but client dict is still building.
                 # Avoid showing "Allocating" eternally when actually stopping
                 status = "Running" if dog.state != DogState.SLEEPING else "Paused"

        sandboxes.append({
            "dog_name": dog.name,
            "claim_name": claim_name,
            "status": status,
            "ip": ip,
            "dog_state": dog.state.value
        })

    state_update = {
        "tick": sim.tick_count,
        "dogs": [
             {
                 "name": dog.name,
                 "breed": dog.breed,
                 "state": dog.state.value,
                 "needs": dog.needs.__dict__,
                 "play_partner": dog.play_partner,
                 "ticks_in_state": dog.ticks_in_state,
                 "latest_bark": dog.latest_bark,
                 "personality": dog.personality.value
             } for dog in sim.dogs.values()
        ],
        "sandboxes": sandboxes
    }
    for client in list(connected_clients):
        try:
             await client.send_json(state_update)
        except Exception:
             if client in connected_clients:
                 connected_clients.remove(client)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
         # Send initial state
         await broadcast_state()
         while True:
             await websocket.receive_text() # Keep connection alive or listen for commands
    except WebSocketDisconnect:
         connected_clients.remove(websocket)
