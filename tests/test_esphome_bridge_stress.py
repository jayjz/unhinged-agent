import pytest
from unittest.mock import AsyncMock, MagicMock
import asyncio

from aioesphomeapi import VoiceAssistantEventType
from core.fsm import AgentState
from services.esphome_bridge import ESPHomeBridge


@pytest.mark.asyncio
async def test_esphome_bridge_rapid_barge_in():
    """Simulates aggressive interrupt mid-turn without loading real models."""
    mock_llm = MagicMock()
    mock_llm.query = AsyncMock(return_value="This is a long response that will be interrupted.")
    mock_llm.close = AsyncMock()

    mock_audio = MagicMock()
    mock_audio.transcribe = AsyncMock(return_value="First command")
    mock_audio.synthesize_speech = AsyncMock(return_value=b"\x00" * 4096)

    bridge = ESPHomeBridge(
        edge_ip="192.168.1.100",
        audio_pipeline=mock_audio,
        llm=mock_llm,
    )

    await bridge._on_voice_event(VoiceAssistantEventType.VOICE_ASSISTANT_RUN_START, {})
    assert bridge.fsm.current_state == AgentState.LISTENING

    await bridge._on_voice_audio(b"\x01" * 1024)

    await bridge._on_voice_event(VoiceAssistantEventType.VOICE_ASSISTANT_STT_END, {})
    assert bridge.fsm.current_state == AgentState.PROCESSING

    # Barge-in before first turn finishes
    await bridge._on_voice_event(VoiceAssistantEventType.VOICE_ASSISTANT_RUN_START, {})
    assert bridge.fsm.current_state == AgentState.LISTENING
    assert len(bridge._current_audio_buffer) == 0

    await asyncio.sleep(0.1)
    assert bridge._processing_task.cancelled() or bridge._processing_task.done()

    await bridge._on_voice_event(VoiceAssistantEventType.VOICE_ASSISTANT_STT_END, {})
    assert bridge.fsm.current_state == AgentState.PROCESSING
