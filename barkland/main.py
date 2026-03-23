from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import Dict, List
import asyncio
import os
import random

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

# Pre-populate some dogs
sim.add_dog(DogProfile(name="Buddy", breed="Golden Retriever", personality=Personality.JOCK, state=DogState.PLAYING))
sim.add_dog(DogProfile(name="Stella", breed="French Bulldog", personality=Personality.DRAMA_QUEEN, state=DogState.SLEEPING))
sim.add_dog(DogProfile(name="Buster", breed="Beagle", personality=Personality.PHILOSOPHER, state=DogState.EATING))

from barkland.agents.dog_agent import DogAgent

connected_clients: List[WebSocket] = []
sandbox_clients: Dict[str, 'SandboxClient'] = {}
dog_agents: Dict[str, DogAgent] = {dog.name: DogAgent(dog) for dog in sim.dogs.values()}

def create_sandbox_for_dog(dog_name: str):
    """Background thread target to allocate SandboxClaim without item locks blocking FastAPI context triggers."""
    if not SandboxClient:
         return
    try:
         client = SandboxClient(template_name="dog-agent-template", namespace="barkland", api_url="http://sandbox-router-svc:8080")
         sandbox_clients[dog_name] = client
         client.__enter__()
    except Exception as e:
         print(f"Error creating sandbox for {dog_name}: {e}")
         sandbox_clients.pop(dog_name, None)

@app.get("/api/dogs")
def get_dogs():
    return [dog.__dict__ for dog in sim.dogs.values()]

@app.post("/api/simulation/start")
async def start_simulation():
    if not sim.is_running:
         # Run in background via asyncio task
         asyncio.create_task(run_simulation())
         return {"status": "Simulation started"}
    return {"status": "Simulation already running"}

@app.post("/api/simulation/stop")
def stop_simulation():
    sim.is_running = False
    return {"status": "Simulation stopped"}

async def run_simulation():
    sim.is_running = True
    
    # Start Sandbox claims background threads allocation
    if SandboxClient:
        for dog in sim.dogs.values():
            if dog.name not in sandbox_clients:
                 threading.Thread(target=create_sandbox_for_dog, args=(dog.name,), daemon=True).start()
                 
    while sim.is_running and sim.tick_count < sim.config.num_ticks:
        await sim.step()
        
        # Trigger Whirlwind Talking lines every 3 tick cycles to avoid saturating limits too tightly
        if sim.tick_count > 5 and sim.tick_count % 3 == 0:
             tasks = []
             for name, dog in sim.dogs.items():
                  agent = dog_agents.get(name)
                  if agent:
                       async def speak_and_update(a_dog, an_agent):
                           try:
                               res = await an_agent.speak()
                               a_dog.latest_bark = f"{res.bark} <span style='font-weight: 600; color:#a855f7; display:block; margin-top:4px; font-size:0.8rem;'>({res.translation})</span>"
                           except Exception as e:
                               print(f"Agent speak error for {a_dog.name}: {e}")
                       tasks.append(speak_and_update(dog, agent))
             if tasks:
                  await asyncio.gather(*tasks)

        await broadcast_state()
        await asyncio.sleep(sim.config.speed_ms / 1000.0)
        
    sim.is_running = False
    
    # Deletion / Cleanup on stop/pause sleep cycles
    for dog_name in list(sandbox_clients.keys()):
        client = sandbox_clients.pop(dog_name, None)
        if client:
             # Run in thread so exit deletion doesn't block async cleanup sequences
             threading.Thread(target=client.__exit__, args=(None, None, None), daemon=True).start()

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
                 status = "Running" if dog.state.value != "SLEEPING" else "Paused"
                 ip = client.base_url or "Dynamic IP Ready"
            else:
                 status = "Bound" if getattr(client, "sandbox_name", None) else "Creating"
        else:
            # Fallback for mock view logic or triggers allocations pending
            status = "Allocating"
            if not SandboxClient:
                 status = "Running" if dog.state.value != "SLEEPING" else "Paused"
                 ip = f"10.64.{i + 1}.12"
                 
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
