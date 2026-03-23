import asyncio
import random
from typing import Dict
from barkland.models.dog import DogProfile, DogState
from barkland.config import SimulationConfig
from barkland.engine.fsm import evaluate_transition
from barkland.engine.needs import update_needs
from barkland.engine.matching import match_play_partners

class SimulationLoop:
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.dogs: Dict[str, DogProfile] = {}
        self.tick_count = 0
        self.rng = random.Random(config.seed)
        self.is_running = False

    def add_dog(self, dog: DogProfile):
        self.dogs[dog.name] = dog

    async def step(self):
        """
        Single tick execution.
        """
        self.tick_count += 1
        
        # 1. Update Needs
        for dog in self.dogs.values():
            update_needs(dog)
            dog.ticks_in_state += 1

        # 2. Gather Play Invitations/Triggers (Internal state for now)
        # For simplicity, let's just evaluate FSM for each dog
        next_states = {}
        for name, dog in self.dogs.items():
             # pass empty play_invitations for now
             next_states[name] = evaluate_transition(dog, [], self.rng)
             
        # 3. Apply state transitions
        for name, next_state in next_states.items():
             dog = self.dogs[name]
             if next_state != dog.state:
                 dog.state = next_state
                 dog.ticks_in_state = 0
                 # Clear play partner if leaving PLAYING
                 if next_state != DogState.PLAYING:
                     dog.play_partner = None

        # 4. Handle Matching (Play)
        playing_dogs = [name for name, dog in self.dogs.items() if dog.state == DogState.PLAYING]
        pairs, unmatched = match_play_partners(playing_dogs)
        
        for d1, d2 in pairs:
            self.dogs[d1].play_partner = d2
            self.dogs[d2].play_partner = d1
            
        for d in unmatched:
             self.dogs[d].play_partner = None

    async def run(self):
        self.is_running = True
        while self.is_running and self.tick_count < self.config.num_ticks:
            await self.step()
            await asyncio.sleep(self.config.speed_ms / 1000.0)
        self.is_running = False
