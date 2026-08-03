import pytest
from unittest.mock import AsyncMock, patch

from core.fsm import AgentState
from services.esphome_bridge import ESPHomeBridge

@pytest.mark.asyncio
@patch('services.esphome_bridge.AudioPipelineService')
@patch('services.esphome_bridge.LLMService')
async def test_esphome_bridge_initialization(mock_llm, mock_audio):
    # Setup mocked services to prevent loading models into VRAM during CI
    bridge = ESPHomeBridge(edge_ip="192.168.1.100")
    
    # Verify proper initial FSM state
    assert bridge.fsm.current_state == AgentState.IDLE
    
    # Close resources
    await bridge.llm.close()