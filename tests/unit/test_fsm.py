import pytest
import random
from barkland.models.dog import DogProfile, DogState, Personality
from barkland.engine.fsm import evaluate_transition

@pytest.fixture
def dog():
    return DogProfile(name="TestDog", breed="Mutt", personality=Personality.PHILOSOPHER)

@pytest.fixture
def rng():
    return random.Random(42)

def test_sleeping_to_eating_when_hungry(dog, rng):
    dog.state = DogState.SLEEPING
    dog.needs.energy = 95
    dog.needs.hunger = 80
    
    next_state = evaluate_transition(dog, [], rng)
    assert next_state == DogState.EATING

def test_sleeping_to_playing_when_bored(dog, rng):
    dog.state = DogState.SLEEPING
    dog.needs.energy = 95
    dog.needs.hunger = 10 # Not hungry
    dog.needs.boredom = 80
    
    # Needs play_invitations to play from sleeping?
    next_state = evaluate_transition(dog, ["invitation"], rng)
    assert next_state == DogState.PLAYING

def test_sleeping_remains_if_tired(dog, rng):
    dog.state = DogState.SLEEPING
    dog.needs.energy = 50 # Tired
    
    next_state = evaluate_transition(dog, [], rng)
    assert next_state == DogState.SLEEPING

def test_eating_to_sleeping_when_full_and_tired(dog, rng):
    dog.state = DogState.EATING
    dog.needs.hunger = 10 # Full
    dog.needs.energy = 20 # Tired
    
    next_state = evaluate_transition(dog, [], rng)
    assert next_state == DogState.SLEEPING

def test_eating_to_playing_when_full_and_bored(dog, rng):
    dog.state = DogState.EATING
    dog.needs.hunger = 10
    dog.needs.energy = 80 # Awake
    dog.needs.boredom = 60
    
    next_state = evaluate_transition(dog, [], rng)
    assert next_state == DogState.PLAYING
