from typing import List, Optional
from pydantic import BaseModel, Field
# from google_adk import LlmAgent, Tool # Assuming ADK imports
class Tool: pass
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
        # self.agent = LlmAgent(
        #     model_name="gemini-2.5-flash", 
        #     instruction=self.instruction,
        #     tools=[self.get_needs_tool(), self.get_surroundings_tool()]
        # )

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
              from google import genai
              from google.genai import types
              from pydantic import BaseModel

              class BarkOutput(BaseModel):
                  bark: str
                  translation: str

              client = genai.Client()
              prompt = (
                  f"You are a dog named {self.profile.name}, a {self.profile.breed}. "
                  f"Your personality is '{self.profile.personality.value}'. "
                  f"Your current state is {self.profile.state.name}. "
                  "Generate your reaction. "
                  "The 'bark' should be a short sound and action description (e.g., 'Woof! *wags tail*'). "
                  "The 'translation' is your humorous internal monologue reflecting your personality and current state. "
                  "Keep it short and immersive."
              )
              if self.profile.state == DogState.SLEEPING:
                   prompt += (
                       " Since you are SLEEPING, the 'bark' needs to be sleeping sounds (e.g., 'Zzz... 😴 *twitch*') "
                       "and the 'translation' MUST be a short, funny dream description starting with 'Sleeping (Dreaming of...)' or similar."
                   )

              response = client.models.generate_content(
                   model='gemini-2.5-flash',
                   contents=prompt,
                   config=types.GenerateContentConfig(
                       response_mime_type="application/json",
                       response_schema=BarkOutput,
                   ),
              )
              import json
              res_json = json.loads(response.text)
              return BarkResponse(bark=res_json['bark'], translation=res_json['translation'])
         except Exception as e:
              # Fallback to static mock responses
              pass


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


    def get_needs_tool(self) -> Tool:
         # ADK Tool skeleton
         def check_needs():
             return self.profile.needs.__dict__
         return Tool(name="check_needs", func=check_needs)
         
    def get_surroundings_tool(self) -> Tool:
         def check_surroundings():
              # Return other dogs state, etc.
              return {"simulation_time": "tick"}
         return Tool(name="check_surroundings", func=check_surroundings)
