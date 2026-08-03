# tests/test_core.py
import pytest
import sqlite3
import asyncio
from unittest.mock import patch, AsyncMock

from core.fsm import AgentState, StateMachine
from tools.notes_db import init_db, save_note_tool, search_notes_tool
import tools.notes_db as notes_db
from services.tts_service import TTSService


# ==========================================
# 1. FSM & BARGE-IN TESTS
# ==========================================
@pytest.mark.asyncio
async def test_fsm_barge_in_logic():
    fsm = StateMachine()

    # Simulate normal flow
    await fsm.transition_to(AgentState.LISTENING)
    await fsm.transition_to(AgentState.PROCESSING)
    await fsm.transition_to(AgentState.SPEAKING)

    # Simulate user interrupting while AI is speaking
    assert fsm.current_state == AgentState.SPEAKING
    success = await fsm.transition_to(AgentState.LISTENING)

    assert success is True
    assert fsm.current_state == AgentState.LISTENING


# ==========================================
# 2. SQLITE RAG MEMORY TESTS
# ==========================================
@pytest.fixture
def temp_db(tmp_path):
    """Creates a temporary SQLite DB for isolated testing."""
    db_file = tmp_path / "test_notes.sqlite"

    # Patch the DB_PATH in the module
    original_path = notes_db.DB_PATH
    notes_db.DB_PATH = str(db_file)

    init_db()  # Initialize tables and FTS5

    yield str(db_file)

    notes_db.DB_PATH = original_path


@pytest.mark.asyncio
async def test_save_and_search_notes(temp_db):
    # 1. Save a note
    save_args = {
        "transcript": "The new ESP32 firmware needs a DMA flush on barge-in.",
        "tags": "esp32, firmware, audio",
    }
    save_result = await save_note_tool(save_args)
    assert "successfully" in save_result.lower()

    # 2. Search for the note using FTS5
    search_args = {"query": "DMA flush"}
    search_result = await search_notes_tool(search_args)

    assert "Found notes:" in search_result
    assert "ESP32 firmware" in search_result
    assert "Tags: esp32, firmware" in search_result


# ==========================================
# 3. TTS HEADER STRIPPING TEST
# ==========================================
@pytest.mark.asyncio
@patch("services.tts_service.httpx.AsyncClient.post")
async def test_kokoro_tts_strips_wav_header(mock_post):
    # Create a fake 44-byte WAV header followed by 10 bytes of "PCM" data
    fake_wav_header = b"RIFF" + (b"\x00" * 40)
    fake_pcm_data = b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a"

    mock_response = AsyncMock()
    mock_response.content = fake_wav_header + fake_pcm_data
    mock_response.raise_for_status = AsyncMock()
    mock_post.return_value = mock_response

    tts = TTSService()
    pcm_output = await tts.synthesize_speech("Test string")

    # Verify the 44-byte RIFF header was stripped for the ESP32 WebSocket
    assert pcm_output == fake_pcm_data
    assert not pcm_output.startswith(b"RIFF")
