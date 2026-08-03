import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
from contextlib import asynccontextmanager

import api.server
from config.settings import settings

# 1. Create fake services that don't use the RTX 4060
mock_audio = MagicMock()
mock_audio.is_speech.return_value = 0.99
mock_audio.transcribe = AsyncMock(return_value="What time is it?")
mock_audio.synthesize_speech = AsyncMock(return_value=b'\x01\x02' * 2048)

mock_llm = MagicMock()
mock_llm.query = AsyncMock(return_value="It is test time.")

# 2. Inject them into the server state
api.server.audio_pipeline = mock_audio
api.server.llm_service = mock_llm

# 3. Disable the real lifespan so we don't load heavy models into VRAM during testing
@asynccontextmanager
async def mock_lifespan(app):
    yield

api.server.app.router.lifespan_context = mock_lifespan

# 4. Initialize test client
client = TestClient(api.server.app)

def test_websocket_full_conversation_loop():
    token = settings.websocket_token
    
    # Connect with the required auth token
    with client.websocket_connect(f"/ws/agent?token={token}") as websocket:
        
        # Send a binary chunk of fake audio (512 samples = 1024 bytes)
        websocket.send_bytes(b'\x00' * 1024)
        
        # Verify the system enters LISTENING state
        data = websocket.receive_json()
        assert data["event"] == "STATE_CHANGE"
        assert data["state"] == "LISTENING"
        
        # Simulate the user stopping talking
        mock_audio.is_speech.return_value = 0.1
        
        # Send enough silent chunks to trigger the silence duration timeout (32 frames)
        for _ in range(32):
            websocket.send_bytes(b'\x00' * 1024)
            
        # Verify the system moves to THINKING
        data = websocket.receive_json()
        assert data["event"] == "STATE_CHANGE"
        assert data["state"] == "THINKING"
        
        # Verify the Transcription is sent back
        data = websocket.receive_json()
        assert data["event"] == "TRANSCRIPT"
        assert data["text"] == "What time is it?"
        
        # Verify the system moves to SPEAKING
        data = websocket.receive_json()
        assert data["event"] == "STATE_CHANGE"
        assert data["state"] == "SPEAKING"
        
        # Verify the binary TTS audio streams back
        audio_bytes = websocket.receive_bytes()
        assert len(audio_bytes) > 0
        
        # Verify the system returns to IDLE
        data = websocket.receive_json()
        assert data["event"] == "STATE_CHANGE"
        assert data["state"] == "IDLE"