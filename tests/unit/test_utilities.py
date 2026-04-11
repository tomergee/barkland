import pytest
import unittest.mock as mock
from barkland.main import generate_unique_dog_names
from barkland.models.dog import DogProfile, DogState, Personality, DogNeeds
from barkland.agents.dog_agent import DogAgent, BarkResponse

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
    
    # Mock Runner
    with mock.patch('barkland.agents.dog_agent.Runner') as MockRunner:
        mock_runner_instance = MockRunner.return_value
        
        captured_new_message = None
        
        async def mock_run_async(user_id, session_id, new_message):
            nonlocal captured_new_message
            captured_new_message = new_message
            
            mock_event = mock.MagicMock()
            mock_event.actions.state_delta = {"bark_response": BarkResponse(bark="Zzz", translation="Sleeping (Dreaming of bacon)")}
            yield mock_event
            
        mock_runner_instance.run_async = mock_run_async
        
        # Call speak
        response = await agent.speak()
        
        # Verify prompt
        assert captured_new_message is not None
        prompt_text = captured_new_message.parts[0].text
        
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
    
    with mock.patch('barkland.agents.dog_agent.Runner') as MockRunner:
        mock_runner_instance = MockRunner.return_value
        
        captured_new_message = None
        
        async def mock_run_async(user_id, session_id, new_message):
            nonlocal captured_new_message
            captured_new_message = new_message
            
            mock_event = mock.MagicMock()
            mock_event.actions.state_delta = {"bark_response": BarkResponse(bark="Crunch", translation="Yum")}
            yield mock_event
            
        mock_runner_instance.run_async = mock_run_async
        
        await agent.speak()
        
        assert captured_new_message is not None
        prompt_text = captured_new_message.parts[0].text
        
        assert "EATING" in prompt_text
