import random
from barkland.models.dog import DogProfile, DogState

def evaluate_transition(
    dog: DogProfile,
    play_invitations: list[str],
    rng: random.Random
) -> DogState:
    """
    Determine the next state. Pure function, no side effects, no LLM.
    Food is always available — no scarcity check needed.
    """
    if dog.state == DogState.SLEEPING:
        if dog.needs.energy >= 90:
            if dog.needs.hunger > 70:
                return DogState.EATING
            if dog.needs.boredom > 60 and len(play_invitations) > 0:
                return DogState.PLAYING
            if dog.needs.hunger > 50 or dog.needs.boredom > 40:
                choices = [DogState.EATING, DogState.PLAYING, DogState.SLEEPING]
                weights = [dog.needs.hunger, dog.needs.boredom, 50]
                return rng.choices(choices, weights=weights, k=1)[0]
        return DogState.SLEEPING

    elif dog.state == DogState.EATING:
        if dog.needs.hunger < 20:
            if dog.needs.energy < 30:
                return DogState.SLEEPING
            if dog.needs.boredom > 50:
                return DogState.PLAYING
            return DogState.SLEEPING
        return DogState.EATING

    elif dog.state == DogState.PLAYING:
        if dog.needs.energy < 30:
            return DogState.SLEEPING
        if dog.needs.hunger > 80:
            return DogState.EATING
        return DogState.PLAYING

    return dog.state
