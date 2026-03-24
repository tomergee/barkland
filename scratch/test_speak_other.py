import asyncio
import os
import random
from barkland.models.dog import DogProfile, DogState, Personality, DogNeeds
from barkland.agents.dog_agent import DogAgent

async def main():
    # SETUP
    states = [DogState.EATING, DogState.PLAYING]
    personalities = [
        Personality.DRAMA_QUEEN, Personality.PHILOSOPHER, Personality.GOSSIP,
        Personality.JOCK, Personality.FOODIE, Personality.GRUMP
    ]
    
    state = random.choice(states)
    personality = random.choice(personalities)
    
    profile = DogProfile(
        name="Sir Barkley",
        breed="Golden Retriever",
        personality=personality,
        state=state,
        needs=DogNeeds(energy=60, hunger=40, boredom=40)
    )
    
    agent = DogAgent(profile)
    print(f"[{personality.name} | {state.name}]")
    
    try:
        response = await agent.speak()
        print(f"Bark: {response.bark}")
        print(f"Translation: {response.translation}")
        print("---")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if not os.getenv("GEMINI_API_KEY"):
         print("WARNING: GEMINI_API_KEY is not set.")
    asyncio.run(main())
