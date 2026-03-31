from typing import List, Optional, Callable
from pydantic import BaseModel, Field
from google.adk.agents import LlmAgent # Assuming ADK imports
from barkland.models.dog import DogProfile, DogState
from barkland.agents.personalities import PERSONALITY_INSTRUCTIONS

# Pydantic models for structured output if needed
class BarkResponse(BaseModel):
    bark: str = Field(description="The bark or action description (e.g., 'bark bark! *tail wag*')")
    translation: str = Field(description="The internal translation of the bark (what the dog is thinking/feeling)")

class DogAgent:
    """
    Dog Agent wrapping an ADK LlmAgent with FSM.
    """
    def __init__(self, profile: DogProfile):
        self.profile = profile
        self.instruction = self._generate_instruction()
        
        # Initialize ADK Agent
        self.agent = LlmAgent(
            name=f"dog_agent_{self.profile.name.lower().replace(' ', '_')}",
            model="gemini-2.5-flash",
            instruction=self.instruction,
            tools=[self.get_needs_tool(), self.get_surroundings_tool()]
        )
    def _generate_instruction(self) -> str:
        base = f"""You are a dog named {self.profile.name}, a {self.profile.breed}.
Your personality type is: {self.profile.personality.value}.
{PERSONALITY_INSTRUCTIONS.get(self.profile.personality, "")}

Your core task is to express your current state and needs through barks, growls, and body language.
You are in a simulation park.

When asked to action or bark:
1. Review your internal state (Needs, current state).
2. Generate a 'bark' (sound + description).
3. Provide a 'translation' (your internal thought process, personality-driven).
"""
        return base

    async def speak(self) -> BarkResponse:
         """
         Generate a bark using Gemini Flash (Bypassed with dummy for local setup trigger visual verification).
         """
         import random
         from barkland.models.dog import Personality, DogState

         try:
              prompt = (
                   f"React to your current state: {self.profile.state.name}. "
                   "The 'bark' needs to be a short sound and action description. "
                   "The 'translation' is your humorous internal monologue reflecting your personality and current state. "
                   "Keep it short and immersive."
              )
              if self.profile.state == DogState.SLEEPING:
                   prompt += (
                       " Since you are SLEEPING, the 'bark' needs to be sleeping sounds (e.g., 'Zzz... 😴 *twitch*') "
                       "and the 'translation' MUST be a short, funny dream description starting with 'Sleeping (Dreaming of...)' or similar."
                   )

              res = await self.agent.run(prompt, response_schema=BarkResponse)
              return BarkResponse(bark=res.bark, translation=res.translation)
         except Exception as e:
              # Do not mask the exception; fail if ADK is missing or errors out
              raise e


         mock_responses = {

             Personality.DRAMA_QUEEN: [
                 ("Aarrff! 😭 *swoons*", "The water bowl is half empty. Surely I am being starved!"),
                 ("Yip yip! 😱 *gasp*", "THAT dog sniffed MY grass! The AUDACITY!"),
                 ("Howl... 😩 *sigh*", "NO ONE looked at me for three whole minutes. I'm fading away.")
             ],
             Personality.PHILOSOPHER: [
                 ("Oooof... 🌌 *stares*", "What is the 'Good Boy'? Is it a title bestowed, or an inherent state?"),
                 ("Rrruf... 🌀 *blinks*", "I chase the red dot, yet it slips away. A symbol of our infinite hubris."),
                 ("Hmph. 🧭 *contemplates*", "To bark, or not to bark. That is the question of the afternoon.")
             ],
             Personality.GOSSIP: [
                 ("Yip! 🗣️ *whispers*", "Did you see Buster sniffing the fire hydrant? Scandalous."),
                 ("Bark! 👀 *points with nose*", "Stella is sleeping. Again. Sloth is a dangerous sin in this park."),
                 ("Grrrr... 🤫 *nods*", "I heard Buddy let the squirrel escape last Tuesday on purpose.")
             ],
             Personality.JOCK: [
                 ("Woof woof! 🎾 *sprints*", "BALL IS LIFE! Run hard, nap hard!"),
                 ("Bark! 🏃‍♂️ *panting*", "Another day, another GAIN. Count the fetched sticks!"),
                 ("Yip! 🏆 *flexes*", "I do full-speed sprints while they sleep. Weakness is not allowed!")
             ],
             Personality.FOODIE: [
                 ("Sniff sniff... 🤤 *licks chops*", "This dry kibble has hints of generic poultry and deep despair."),
                 ("Slurp! 💧 *winks*", "A 2025 vintage toilet water. Exquisite mouthfeel. Notes of porcelain."),
                 ("Awoo! 🥩 *demands gourmet*", "I only eat when the temperature is precisely optimal, obviously.")
             ],
             Personality.GRUMP: [
                 ("Grrr. 😒 *rolls eyes*", "Why is everyone moving? Stop moving. It's annoying."),
                 ("Snort. 🛑 *glares*", "Another day, another squirrel that refuses to get off my lawn."),
                 ("Sigh. 💤 *curls up*", "If I have to fetch that stick one more time, I'm retiring.")
             ],
         }

         if self.profile.state == DogState.SLEEPING:
              dreams = [
                  "chasing giant squirrels made of bacon",
                  "swimming in a pool filled with peanut butter",
                  "catching the ultimate red laser dot",
                  "the perfect tennis ball that never bounces away",
                  "digging to the center of the Earth to find sausages"
              ]
              dream = random.choice(dreams)
              return BarkResponse(bark="Zzz... 😴 *twitch*", translation=f"Sleeping (Dreaming of {dream})")

         lines = mock_responses.get(self.profile.personality, [("Woof!", "Barking.")])
         idx = random.randint(0, len(lines)-1)
         return BarkResponse(bark=lines[idx][0], translation=lines[idx][1])


    def get_needs_tool(self) -> Callable:
         # ADK Tool skeleton
         def check_needs():
             return self.profile.needs.__dict__
         return check_needs

    def get_surroundings_tool(self) -> Callable:
         def check_surroundings():
              # Return other dogs state, etc.
              return {"simulation_time": "tick"}
         return check_surroundings
