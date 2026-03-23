from dataclasses import dataclass, field
from typing import Optional

@dataclass
class SimulationConfig:
    num_dogs: int = 5
    num_ticks: int = 200
    speed_ms: int = 1000           # delay between ticks in milliseconds
    seed: int = 42
    log_file: Optional[str] = None # path to write JSON event log
