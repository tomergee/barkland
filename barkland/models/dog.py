from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
import random

class DogState(Enum):
    SLEEPING = "sleeping"
    EATING = "eating"
    PLAYING = "playing"

class Personality(Enum):
    DRAMA_QUEEN = "drama_queen"
    PHILOSOPHER = "philosopher"
    GOSSIP = "gossip"
    JOCK = "jock"
    FOODIE = "foodie"
    GRUMP = "grump"

@dataclass
class DogNeeds:
    energy: float = field(default_factory=lambda: random.uniform(40, 80))
    hunger: float = field(default_factory=lambda: random.uniform(20, 50))
    boredom: float = field(default_factory=lambda: random.uniform(30, 60))

    def clamp(self):
        self.energy = max(0.0, min(100.0, self.energy))
        self.hunger = max(0.0, min(100.0, self.hunger))
        self.boredom = max(0.0, min(100.0, self.boredom))

@dataclass
class DogProfile:
    name: str
    breed: str
    personality: Personality
    state: DogState = DogState.SLEEPING
    needs: DogNeeds = field(default_factory=DogNeeds)
    play_partner: Optional[str] = None
    ticks_in_state: int = 0
    latest_bark: str = ""
