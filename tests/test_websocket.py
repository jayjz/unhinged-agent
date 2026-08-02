import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from api.server import app

# FastAPI TestClient allows us to test WebSockets synchronously
client = TestClient(app)

@patch("api.websocket.AudioPipelineService")
@patch("api.websocket.LLMService")
def test_websocket_full_conversation_loop(mock_llm, mock_audio):
    # 1. Setup the Mocks (Fake the ML models)
    mock_audio_instance = mock_audio.return_value
    mock_audio_instance.is_speech.return_value = 0.99  # Simulate loud speech
    mock_audio_instance.transcribe = AsyncMock(return_value="What time is it?")
    mock_audio_instance.synthesize_speech = AsyncMock(return_value=b'\x01\x02' * 2048)
    
    mock_llm_instance = mock_llm.return_value
    mock_llm_instance.query = AsyncMock(return_value="It is test time.")

    # 2. Connect to the WebSocket
    with client.websocket_connect("/ws/agent") as websocket:
        
        # 3. Send a binary chunk of fake audio
        websocket.send_bytes(b'\x00' * 1024)
        
        # 4. Verify the system enters LISTENING state
        data = websocket.receive_json()
        assert data["event"] == "STATE_CHANGE"
        assert data["state"] == "LISTENING"
        
        # 5. Simulate the user stopping talking (is_speech drops below threshold)
        mock_audio_instance.is_speech.return_value = 0.1
        
        # Send enough silent chunks to trigger the silence duration timeout (~25 frames)
        for _ in range(25):
            websocket.send_bytes(b'\x00' * 1024)
            
        # 6. Verify the system moves to THINKING
        data = websocket.receive_json()
        assert data["event"] == "STATE_CHANGE"
        assert data["state"] == "THINKING"
        
        # 7. Verify the Transcription is sent back
        data = websocket.receive_json()
        assert data["event"] == "TRANSCRIPT"
        assert data["text"] == "What time is it?"
        
        # 8. Verify the system moves to SPEAKING
        data = websocket.receive_json()
        assert data["event"] == "STATE_CHANGE"
        assert data["state"] == "SPEAKING"
        
        # 9. Verify the binary TTS audio streams back
        audio_bytes = websocket.receive_bytes()
        assert len(audio_bytes) > 0
        
        # 10. Verify the system returns to IDLE
        data = websocket.receive_json()
        assert data["event"] == "STATE_CHANGE"
        assert data["state"] == "IDLE"