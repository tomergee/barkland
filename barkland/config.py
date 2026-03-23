from dataclasses import dataclass, field
from typing import Optional

import os

@dataclass
class SimulationConfig:
    num_dogs: int = int(os.getenv("NUM_DOGS", 5))
    num_ticks: int = int(os.getenv("NUM_TICKS", 200))
    speed_ms: int = int(os.getenv("SPEED_MS", 1000))  # delay between ticks in milliseconds
    seed: int = int(os.getenv("SEED", 42))
    log_file: Optional[str] = os.getenv("LOG_FILE") # path to write JSON event log
