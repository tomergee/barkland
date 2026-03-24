import asyncio
import os
import random
from barkland.models.dog import DogProfile, DogState, Personality, DogNeeds
from barkland.agents.dog_agent import DogAgent

async def main():
    # Setup profile
    profile = DogProfile(
        name="Sir Barkley",
        breed="Golden Retriever",
        personality=Personality.PHILOSOPHER,
        state=DogState.SLEEPING,
        needs=DogNeeds(energy=20, hunger=40, boredom=50)
    )
    
    agent = DogAgent(profile)
    print(f"Testing speak() for {profile.name} in state {profile.state}...")
    
    try:
        response = await agent.speak()
        print("\n=== Speak Response ===")
        print(f"Bark: {response.bark}")
        print(f"Translation: {response.translation}")
        print("=======================")
    except Exception as e:
        print(f"\nError running speak(): {e}")

if __name__ == "__main__":
    # Ensure GEMINI_API_KEY is available in Python environment
    if not os.getenv("GEMINI_API_KEY"):
        print("WARNING: GEMINI_API_KEY is not set in environment.")
    asyncio.run(main())
