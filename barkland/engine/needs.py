from barkland.models.dog import DogProfile, DogState

NEED_DELTAS = {
    DogState.SLEEPING: {"energy": +8, "hunger": +2, "boredom": +1},
    DogState.EATING:   {"energy": -1, "hunger": -10, "boredom": +2},
    DogState.PLAYING:  {"energy": -5, "hunger": +3, "boredom": -8},
}

def update_needs(dog: DogProfile):
    """
    Update needs based on current state.
    """
    deltas = NEED_DELTAS.get(dog.state, {})
    for need, delta in deltas.items():
        current_val = getattr(dog.needs, need)
        setattr(dog.needs, need, current_val + delta)
    dog.needs.clamp()
