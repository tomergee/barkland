import pytest
from barkland.models.dog import DogProfile, DogState, Personality
from barkland.engine.needs import update_needs, NEED_DELTAS

def test_needs_tick_updates_sleeping():
    dog = DogProfile(name="TestDog", breed="Mutt", personality=Personality.PHILOSOPHER)
    dog.state = DogState.SLEEPING
    dog.needs.energy = 50
    dog.needs.hunger = 50
    dog.needs.boredom = 50
    
    update_needs(dog)
    # Sleeping increase energy by 8, hunger by 2, boredom by 1
    assert dog.needs.energy == 58
    assert dog.needs.hunger == 52
    assert dog.needs.boredom == 51

def test_needs_tick_updates_eating():
    dog = DogProfile(name="TestDog", breed="Mutt", personality=Personality.PHILOSOPHER)
    dog.state = DogState.EATING
    dog.needs.energy = 50
    dog.needs.hunger = 50
    dog.needs.boredom = 50
    
    update_needs(dog)
    # Eating decrease energy by -1, hunger by -10, boredom by 2
    assert dog.needs.energy == 49
    assert dog.needs.hunger == 40
    assert dog.needs.boredom == 52

def test_needs_clamps_at_max():
    dog = DogProfile(name="TestDog", breed="Mutt", personality=Personality.PHILOSOPHER)
    dog.state = DogState.SLEEPING
    dog.needs.energy = 98
    
    update_needs(dog)
    assert dog.needs.energy == 100 # clamped at 100
