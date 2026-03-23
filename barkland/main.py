from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, List
import asyncio
from barkland.config import SimulationConfig
from barkland.engine.simulation import SimulationLoop
from barkland.models.dog import DogProfile, Personality, DogState

app = FastAPI()

# In-memory Simulation Instance for simplicity
config = SimulationConfig(num_ticks=500)
sim = SimulationLoop(config)

# Pre-populate some dogs
sim.add_dog(DogProfile(name="Buddy", breed="Golden Retriever", personality=Personality.JOCK, state=DogState.PLAYING))
sim.add_dog(DogProfile(name="Stella", breed="French Bulldog", personality=Personality.DRAMA_QUEEN, state=DogState.SLEEPING))
sim.add_dog(DogProfile(name="Buster", breed="Beagle", personality=Personality.PHILOSOPHER, state=DogState.EATING))

connected_clients: List[WebSocket] = []

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
    while sim.is_running and sim.tick_count < sim.config.num_ticks:
        await sim.step()
        await broadcast_state()
        await asyncio.sleep(sim.config.speed_ms / 1000.0)
    sim.is_running = False

async def broadcast_state():
    state_update = {
        "tick": sim.tick_count,
        "dogs": [
             {
                 "name": dog.name,
                 "state": dog.state.value,
                 "needs": dog.needs.__dict__,
                 "play_partner": dog.play_partner,
                 "ticks_in_state": dog.ticks_in_state,
                 "latest_bark": dog.latest_bark
             } for dog in sim.dogs.values()
        ]
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
