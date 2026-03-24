import pytest
import unittest.mock as mock
from barkland.main import generate_unique_dog_names
from barkland.models.dog import DogProfile, DogState, Personality, DogNeeds
from barkland.agents.dog_agent import DogAgent

def test_generate_unique_dog_names_count():
    # Test generating 5 names
    names = generate_unique_dog_names(5)
    assert len(names) == 5
    # Verify uniqueness
    assert len(set(names)) == 5

def test_generate_unique_dog_names_large_count():
    # Test generating 50 names (ensures unique combos or fallback executes)
    names = generate_unique_dog_names(50)
    assert len(names) == 50
    assert len(set(names)) == 50

@pytest.mark.asyncio
async def test_speak_prompt_includes_sleeping_rule():
    # Setup profile in SLEEPING state
    profile = DogProfile(
        name="Sir Barkley", 
        breed="Golden Retriever", 
        personality=Personality.PHILOSOPHER,
        state=DogState.SLEEPING
    )
    agent = DogAgent(profile)
    
    # Mock GenAI client
    with mock.patch('google.genai.Client') as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.models.generate_content.return_value.text = '{"bark": "Zzz", "translation": "Sleeping (Dreaming of bacon)"}'
        
        # Call speak
        response = await agent.speak()
        
        # Verify prompt contained specific SLEEPING instructions
        called_args = mock_instance.models.generate_content.call_args
        prompt_text = called_args.kwargs['contents']
        
        assert "Sir Barkley" in prompt_text
        assert "SLEEPING" in prompt_text
        assert "Dreaming of" in prompt_text or "MUST be a short, funny dream description" in prompt_text

@pytest.mark.asyncio
async def test_speak_prompt_includes_eating_rule():
    profile = DogProfile(
        name="Sir Barkley", 
        breed="Golden Retriever", 
        personality=Personality.FOODIE,
        state=DogState.EATING
    )
    agent = DogAgent(profile)
    
    with mock.patch('google.genai.Client') as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.models.generate_content.return_value.text = '{"bark": "Crunch", "translation": "Yum"}'
        
        await agent.speak()
        
        called_args = mock_instance.models.generate_content.call_args
        prompt_text = called_args.kwargs['contents']
        
        assert "Sir Barkley" in prompt_text
        assert "EATING" in prompt_text
