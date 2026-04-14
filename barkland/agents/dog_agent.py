from typing import List, Optional, Callable
from pydantic import BaseModel, Field
from google.adk.agents import LlmAgent # Assuming ADK imports
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types
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
            name=f"dog_agent_{self.profile.name.lower().replace(' ', '_').replace('.', '')}",
            model="gemini-2.5-flash-lite",
            instruction=self.instruction,
            tools=[self.get_needs_tool(), self.get_surroundings_tool(), self.get_sniff_tool()],
            output_schema=BarkResponse,
            output_key="bark_response"
        )
    def _generate_instruction(self) -> str:
        base = f"""You are a dog named {self.profile.name}, a {self.profile.breed}.
Your personality type is: {self.profile.personality.value}.
{PERSONALITY_INSTRUCTIONS.get(self.profile.personality, "")}

Your core task is to express your current state and needs through barks, growls, and body language.
You are in a simulation park.
You can use tools to check your needs or sniff around for context.

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

         prompt = (
              f"React to your current state: {self.profile.state.name}. "
              "The 'bark' needs to be a short sound and action description. "
              "The 'translation' is your humorous internal monologue reflecting your personality and current state. "
              "You can be influenced by the examples but invent your own style reflecting your personality, also keep it short."
         )
         if self.profile.state == DogState.SLEEPING:
              prompt += (
                  " Since you are SLEEPING, the 'bark' needs to be sleeping sounds (e.g., 'Zzz... 😴 *twitch*') "
                  "and the 'translation' MUST be a short, funny dream description starting with 'Sleeping (Dreaming of...)' or similar."
              )


         try:
              session_service = InMemorySessionService()
              runner = Runner(
                  app_name="barkland",
                  agent=self.agent,
                  session_service=session_service,
                  auto_create_session=True
              )
              
              new_message = types.Content(parts=[types.Part(text=prompt)])
              
              from google.adk.utils.context_utils import Aclosing
              import asyncio
              
              async def _run():
                  async with Aclosing(runner.run_async(
                      user_id="user",
                      session_id="session_1",
                      new_message=new_message,
                  )) as agen:
                      async for event in agen:
                          if event.actions and event.actions.state_delta:
                              res = event.actions.state_delta.get("bark_response")
                              if res:
                                  if isinstance(res, dict):
                                      return BarkResponse(bark=res.get("bark"), translation=res.get("translation"))
                                  return res
                  raise Exception("Failed to get bark response from ADK")
              
              try:
                  return await asyncio.wait_for(_run(), timeout=2.0)
              except asyncio.TimeoutError:
                  print("Gemini call timed out, falling back to mock")
                  return self.get_mock_response()
         except Exception as e:
              print(f"ADK error: {e}")
              raise e

    def get_mock_response(self) -> BarkResponse:
         import random
         from barkland.models.dog import Personality, DogState

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

    def get_sniff_tool(self) -> Callable:
         def sniff_around():
              """Sniff the ground to find interesting smells."""
              import random
              smells = [
                  "a hint of bacon from a nearby picnic",
                  "the distinct scent of a rival cat",
                  "fresh grass and morning dew",
                  "an old tennis ball buried nearby",
                  "the trail of a squirrel"
              ]
              return {"smell": random.choice(smells)}
         return sniff_around
