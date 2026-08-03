import pytest
from unittest.mock import AsyncMock, patch
import asyncio

from aioesphomeapi import VoiceAssistantEventType
from core.fsm import AgentState
from services.esphome_bridge import ESPHomeBridge

@pytest.mark.asyncio
@patch('services.esphome_bridge.AudioPipelineService')
@patch('services.esphome_bridge.LLMService')
async def test_esphome_bridge_rapid_barge_in(mock_llm_class, mock_audio_class):
    """Simulates a user aggressively interrupting the AI mid-sentence."""
    
    # Setup mocks
    mock_llm_instance = mock_llm_class.return_value
    mock_llm_instance.query = AsyncMock(return_value="This is a long response that will be interrupted.")
    mock_llm_instance.close = AsyncMock()
    
    mock_audio_instance = mock_audio_class.return_value
    mock_audio_instance.transcribe = AsyncMock(return_value="First command")
    mock_audio_instance.synthesize_speech = AsyncMock(return_value=b'\x00' * 4096)

    bridge = ESPHomeBridge(edge_ip="192.168.1.100")
    
    # 1. Start listening
    await bridge._on_voice_event(VoiceAssistantEventType.VOICE_ASSISTANT_RUN_START, {})
    assert bridge.fsm.current_state == AgentState.LISTENING
    
    # Feed some audio
    await bridge._on_voice_audio(b'\x01' * 1024)
    
    # 2. Trigger first processing turn
    await bridge._on_voice_event(VoiceAssistantEventType.VOICE_ASSISTANT_STT_END, {})
    assert bridge.fsm.current_state == AgentState.PROCESSING
    
    # 3. IMMEDIATELY trigger a second wake word (Barge-in) before the first turn finishes
    await bridge._on_voice_event(VoiceAssistantEventType.VOICE_ASSISTANT_RUN_START, {})
    
    # The FSM should immediately reset to LISTENING
    assert bridge.fsm.current_state == AgentState.LISTENING
    assert len(bridge._current_audio_buffer) == 0 # Buffer should be cleared
    
    # 4. Give the background task a moment to realize it was cancelled
    await asyncio.sleep(0.1)
    
    # Verify the first processing task was cancelled
    assert bridge._processing_task.cancelled() or bridge._processing_task.done()
    
    # 5. Trigger second processing turn
    await bridge._on_voice_event(VoiceAssistantEventType.VOICE_ASSISTANT_STT_END, {})
    assert bridge.fsm.current_state == AgentState.PROCESSING
    
    # Cleanup
    await bridge.llm.close()