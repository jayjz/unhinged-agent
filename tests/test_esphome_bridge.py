import pytest
from unittest.mock import AsyncMock, MagicMock

from core.fsm import AgentState
from services.esphome_bridge import ESPHomeBridge


@pytest.mark.asyncio
async def test_esphome_bridge_initialization():
    """Bridge must accept injected services and never load VRAM models itself."""
    mock_audio = MagicMock()
    mock_llm = MagicMock()
    mock_llm.close = AsyncMock()

    bridge = ESPHomeBridge(
        edge_ip="192.168.1.100",
        audio_pipeline=mock_audio,
        llm=mock_llm,
    )

    assert bridge.fsm.current_state == AgentState.IDLE
    assert bridge.audio_pipeline is mock_audio
    assert bridge.llm is mock_llm


@pytest.mark.asyncio
async def test_esphome_bridge_rejects_missing_services():
    with pytest.raises(ValueError, match="shared audio_pipeline"):
        ESPHomeBridge(edge_ip="192.168.1.100", audio_pipeline=None, llm=MagicMock())
