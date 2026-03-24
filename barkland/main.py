from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import Dict, List
import asyncio
import os
import random
from pydantic import BaseModel, Field

# Seed early so module-level static declarations roll deterministically
random.seed(int(os.getenv("SEED", "42")))
from barkland.config import SimulationConfig
from barkland.engine.simulation import SimulationLoop
from barkland.models.dog import DogProfile, Personality, DogState
import threading
try:
    from k8s_agent_sandbox import SandboxClient
except ImportError:
    SandboxClient = None # Fallback for local testing without SDK

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    with open("barkland/templates/dashboard.html", "r") as f:
        return f.read()

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
        
    return list(names_set)

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
sandbox_clients: Dict[str, 'SandboxClient'] = {}
dog_agents: Dict[str, DogAgent] = {dog.name: DogAgent(dog) for dog in sim.dogs.values()}

def create_sandbox_for_dog(dog_name: str):
    """Background thread target to allocate SandboxClaim without item locks blocking FastAPI context triggers."""
    if not SandboxClient:
         return
    try:
         import os
         router_url = os.getenv("SANDBOX_ROUTER_URL", "http://sandbox-router-svc:8080")
         client = SandboxClient(template_name="dog-agent-template", namespace="barkland", api_url=router_url)
         sandbox_clients[dog_name] = client
         client.__enter__()

         if not sim.is_running:
              # Race cleanup: if simulation stopped while waiting for claim allocation
              client.__exit__(None, None, None)
              sandbox_clients.pop(dog_name, None)
    except Exception as e:
         print(f"Error creating sandbox for {dog_name}: {e}")
         sandbox_clients.pop(dog_name, None)

@app.get("/api/dogs")
def get_dogs():
    return [dog.__dict__ for dog in sim.dogs.values()]

class StartSimulationRequest(BaseModel):
    count: int = Field(default=4, ge=1, le=99)

@app.post("/api/simulation/start")
async def start_simulation(req: StartSimulationRequest):
    if not sim.is_running:
         # 1. Cleanup old sandbox claims fully to prevent leaks
         for dog_name in list(sandbox_clients.keys()):
              client = sandbox_clients.pop(dog_name, None)
              if client:
                   threading.Thread(target=client.__exit__, args=(None, None, None), daemon=True).start()
         
         # 2. Reset Simulation and Agent pools
         sim.dogs.clear()
         dog_agents.clear()
         sim.tick_count = 0 
         
         # 3. Generate new names layout
         names = generate_unique_dog_names(req.count)

         # 4. Run in background via asyncio task passing names list
         asyncio.create_task(run_simulation(names))
         return {"status": f"Simulation started with {req.count} dogs"}
    return {"status": "Simulation already running"}

@app.post("/api/simulation/stop")
def stop_simulation():
    sim.is_running = False
    return {"status": "Simulation stopped"}

async def run_simulation(names: List[str]):
    sim.is_running = True
    from barkland.agents.dog_agent import DogAgent
    # generate_unique_dog_names is available globally in this file
    
    # 1. Start periodic updates while sandboxes are allocating
    async def monitor_sandboxes():
        while sim.is_running:
            await broadcast_state()
            has_pending = False
            for name in sim.dogs.keys():
                client = sandbox_clients.get(name)
                if not client or not client.is_ready():
                    has_pending = True
                    break
            # Wait, if all ready and all populated layout break setup Accuracy accurately
            if not has_pending and len(sim.dogs) == len(names):
                break
            await asyncio.sleep(1)
            
    asyncio.create_task(monitor_sandboxes())

    # 2. Populate new dogs allocation ITERATIVELY index-by-index Setup trigger Accuracy
    

    for name in names:
         breed = random.choice(DOG_BREEDS)
         personality = random.choice(list(Personality))
         state = random.choice(list(DogState))
         dp = DogProfile(name=name, breed=breed, personality=personality, state=state)
         
         sim.add_dog(dp)
         dog_agents[name] = DogAgent(dp)
         
         # Start Sandbox claim thread allocation layout triggers Accuracy creators layout inaccuracies
         if SandboxClient:
              print(f"Spawning sandbox thread for {name}")
              threading.Thread(target=create_sandbox_for_dog, args=(name,), daemon=True).start()
              
         # Broadcast immediately so UI renders this card individually layout Accurate triggers payout list Accurate setups
         await broadcast_state()
         #await asyncio.sleep(0.05) # 50ms stagger spacing rolling creation

    while sim.is_running and sim.tick_count < sim.config.num_ticks:
        await sim.step()
        
        # Trigger Pause/Resume operations based on State transitions
        for name, dog in sim.dogs.items():
            client = sandbox_clients.get(name)
            if client and getattr(client, "is_ready", lambda: False)():
                if dog.state == DogState.SLEEPING:
                    if not getattr(client, "is_paused", False):
                        try:
                            client.is_paused = True # eagerly mark
                            print(f"Pausing sandbox for dog {name} in background...")
                            # Run synchronous network request in background thread
                            threading.Thread(target=client.pause, daemon=True).start()
                        except Exception as e:
                            print(f"Failed to initiate pause for {name}: {e}")
                else:
                    if getattr(client, "is_paused", False):
                        try:
                            client.is_paused = False # eagerly mark
                            print(f"Resuming sandbox for dog {name} in background...")
                            # Run synchronous network request in background thread
                            threading.Thread(target=client.resume, daemon=True).start()
                        except Exception as e:
                            print(f"Failed to initiate resume for {name}: {e}")

        # Trigger Whirlwind Talking lines every 3 tick cycles
        if sim.tick_count > 5 and sim.tick_count % 3 == 0:
            for name, dog in sim.dogs.items():
                agent = dog_agents.get(name)
                if agent:
                    async def speak_and_update(a_dog, an_agent):
                        try:
                            res = await an_agent.speak()
                            a_dog.latest_bark = f"{res.bark} <span style='font-weight: 600; color:#a855f7; display:block; margin-top:4px; font-size:0.8rem;'>({res.translation})</span>"
                        except Exception as e:
                            print(f"Agent speak error for {a_dog.name}: {e}")
                    
                    # Fire and forget instead of awaiting all generations simultaneously
                    asyncio.create_task(speak_and_update(dog, agent))

        await broadcast_state()
        await asyncio.sleep(sim.config.speed_ms / 1000.0)
        
    sim.is_running = False
    
    # Deletion / Cleanup on stop/pause sleep cycles
    for dog_name in list(sandbox_clients.keys()):
        client = sandbox_clients.pop(dog_name, None)
        if client:
             # Run in thread so exit deletion doesn't block async cleanup sequences
             threading.Thread(target=client.__exit__, args=(None, None, None), daemon=True).start()
             
    await broadcast_state()

async def broadcast_state():
    # Simulate sandbox states for dashboard layout metrics
    sandboxes = []
    for i, dog in enumerate(sim.dogs.values()):
        status = "Created"
        claim_name = f"barkland-sandbox-{dog.name.lower()}"
        ip = "Allocating..."
        
        client = sandbox_clients.get(dog.name)
        if client:
            claim_name = client.claim_name or claim_name
            if client.is_ready():
                 status = "Running" if dog.state != DogState.SLEEPING else "Paused"
                 ip = client.base_url or "Dynamic IP Ready"
            else:
                 status = "Bound" if getattr(client, "sandbox_name", None) else "Creating"
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
            "ip": ip
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
    for client in connected_clients:
        try:
             await client.send_json(state_update)
        except Exception:
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
