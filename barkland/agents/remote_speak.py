import argparse
import asyncio
import json
import sys
from barkland.models.dog import DogProfile, DogState, Personality, DogNeeds
from barkland.agents.dog_agent import DogAgent

async def main():
    parser = argparse.ArgumentParser(description="Run dog agent speak in sandbox")
    parser.add_argument("--name", required=True)
    parser.add_argument("--breed", required=True)
    parser.add_argument("--personality", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--energy", type=float, required=True)
    parser.add_argument("--hunger", type=float, required=True)
    parser.add_argument("--boredom", type=float, required=True)
    parser.add_argument("--model", default="gemini-2.5-flash-lite")
    
    args = parser.parse_args()
    
    try:
        profile = DogProfile(
            name=args.name,
            breed=args.breed,
            personality=Personality(args.personality),
            state=DogState(args.state),
            needs=DogNeeds(energy=args.energy, hunger=args.hunger, boredom=args.boredom)
        )
        
        agent = DogAgent(profile, model=args.model)
        res = await agent.speak()
        
        # Output JSON to stdout
        print(json.dumps({"bark": res.bark, "translation": res.translation}))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
