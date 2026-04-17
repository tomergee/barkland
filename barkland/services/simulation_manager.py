import asyncio
import time
import logging
import random
from typing import List, Dict
from barkland.models.dog import DogProfile, DogState, Personality
from barkland.config import SimulationConfig
from barkland.engine.simulation import SimulationLoop
from barkland.agents.dog_agent import DogAgent
from barkland.services.sandbox_manager import sandbox_clients, create_sandbox_for_dog, speak_and_update, patch_sandbox_replicas, global_sandbox_client

logger = logging.getLogger(__name__)

DOG_BREEDS = ["Golden Retriever", "French Bulldog", "Beagle", "Poodle", "Husky", "Corgi", "Dachshund"]
DOG_PREFIXES = ["Sir", "Lady", "Captain", "Baron", "Count", "Professor", "Doctor", "Agent", "Chief", "Major"]
DOG_NAMES = ["Barkley", "Noodles", "Wags", "Waffles", "Biscuit", "Coco", "Peanut", "Luna", "Boots", "Daisy", "Buster", "Rex", "Stella", "Buddy"]
DOG_SUFFIXES = ["von Sniff", "the Great", "of Barkland", "III", "Jr.", "the Destroyer", "the Fast", "the Brave"]

def generate_unique_dog_names(count: int) -> List[str]:
    names_set = set()
    attempts = 0
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
    
    while len(names_set) < count:
        names_set.add(f"Pup-{len(names_set) + 1}")
    return sorted(list(names_set))

config = SimulationConfig(num_ticks=500)
sim = SimulationLoop(config)
dog_agents: Dict[str, DogAgent] = {}
connected_clients = []

async def broadcast_state():
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
            status = "Allocating"
            status = "Running" if dog.state != DogState.SLEEPING else "Paused"
            ip = f"10.64.{i + 1}.12"

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

async def run_simulation(names: List[str]):
    sim.is_running = True
    sim.start_time = time.time()
    
    async def monitor_sandboxes():
        while sim.is_running:
            await broadcast_state()
            has_pending = False
            for name in sim.dogs.keys():
                client = sandbox_clients.get(name)
                if not client or isinstance(client, dict):
                    has_pending = True
                    break
            if not has_pending and len(sim.dogs) == len(names):
                break
            await asyncio.sleep(1)
            
    monitor_task = asyncio.create_task(monitor_sandboxes())

    try:
        for name in names:
            if not sim.is_running:
                break
            breed = random.choice(DOG_BREEDS)
            personality = random.choice(list(Personality))
            state = random.choice(list(DogState))
            dp = DogProfile(name=name, breed=breed, personality=personality, state=state)
            
            sim.add_dog(dp)
            dog_agents[name] = DogAgent(dp)
             
            if global_sandbox_client:
                 print(f"Spawning sandbox task for {name}")
                 sandbox_clients[name] = {"status": "Creating", "claim_name": f"barkland-sandbox-{name.lower()}"}
                 asyncio.create_task(create_sandbox_for_dog(name))
                  
            await broadcast_state()
            await asyncio.sleep(0.05) # 50ms stagger spacing

        while sim.is_running and sim.tick_count < sim.config.num_ticks:
            await sim.step()
            
            for name, dog in sim.dogs.items():
                if dog.ticks_in_state == 0:
                    logger.info(f"State Change: Dog {name} transitioned to {dog.state.value}")
                    
                client = sandbox_clients.get(name)
                if client and not isinstance(client, dict):
                    if dog.state == DogState.SLEEPING and (time.time() - getattr(sim, "start_time", 0) >= 15):
                        if not getattr(client, "is_paused", False):
                            try:
                                client.is_paused = True
                                print(f"Pausing sandbox for dog {name} in background...")
                                asyncio.create_task(asyncio.to_thread(patch_sandbox_replicas, client, 0))
                            except Exception as e:
                                print(f"Failed to initiate pause for {name}: {e}")
                    else:
                        if getattr(client, "is_paused", False):
                            try:
                                client.is_paused = False
                                print(f"Resuming sandbox for dog {name} in background...")
                                asyncio.create_task(asyncio.to_thread(patch_sandbox_replicas, client, 1))
                            except Exception as e:
                                print(f"Failed to initiate resume for {name}: {e}")

            if sim.tick_count > 0 and sim.tick_count % 2 == 0:
                active_dogs = list(sim.dogs.items())
                active_dogs.sort(key=lambda x: x[0])
                
                num_dogs = len(active_dogs)
                if num_dogs > 0:
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

            if sim.tick_count % 3 == 0 or sim.tick_count >= sim.config.num_ticks:
                await broadcast_state()
                
            await asyncio.sleep(sim.config.speed_ms / 1000.0)
            
    except Exception as e:
        logger.error(f"Error in run_simulation: {e}")
    finally:
        if not monitor_task.done():
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
                
        sim.is_running = False
        
        for dog_name in list(sandbox_clients.keys()):
            sandbox = sandbox_clients.pop(dog_name, None)
            if sandbox and not isinstance(sandbox, dict):
                asyncio.create_task(sandbox.terminate())
                 
        await broadcast_state()
