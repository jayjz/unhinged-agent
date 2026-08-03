import asyncio
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from config.settings import settings
from core.fsm import AgentState, StateMachine
from services.audio_pipeline import AudioPipelineService
from services.llm_service import LLMService

router = APIRouter()


@router.websocket("/ws/agent")
async def websocket_agent_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("ESP32-S3-BOX-3B connected via WebSocket.")

    fsm = StateMachine()
    audio_pipeline = AudioPipelineService()
    llm = LLMService()

    # Network buffering: handles Wi-Fi fragmentation [123]
    network_buffer = bytearray()
    audio_buffer = bytearray()

    # VAD Silero strictly requires exactly 512 samples (1024 bytes for 16-bit) [18]
    VAD_FRAME_SIZE_BYTES = 1024

    silent_frames_count = 0
    max_silent_frames = int(
        (settings.SILENCE_DURATION_MS / 1000.0)
        / (VAD_FRAME_SIZE_BYTES / 2 / settings.SAMPLE_RATE)
    )

    active_tasks = set()

    def cancel_active_tasks():
        """Safely terminates LLM/TTS generation without crashing the socket."""
        for task in active_tasks:
            if not task.done():
                task.cancel()
        active_tasks.clear()

    try:
        while True:
            # 1. Catch fragmented Wi-Fi payloads
            data = await websocket.receive_bytes()
            network_buffer.extend(data)

            # 2. Process only when we have a full VAD frame
            while len(network_buffer) >= VAD_FRAME_SIZE_BYTES:
                frame_bytes = network_buffer[:VAD_FRAME_SIZE_BYTES]
                del network_buffer[:VAD_FRAME_SIZE_BYTES]

                frame_np = (
                    np.frombuffer(frame_bytes, dtype=np.int16).astype(np.float32)
                    / 32768.0
                )
                speech_prob = audio_pipeline.is_speech(frame_np)

                # ==========================================
                # BARGE-IN DETECTION: [SPEAKING] -> [LISTENING]
                # ==========================================
                if (
                    fsm.current_state in (AgentState.SPEAKING, AgentState.PROCESSING)
                    and speech_prob > settings.VAD_THRESHOLD
                ):
                    logger.warning(
                        "Barge-in detected! Halting generation and flushing ESP32 buffers."
                    )

                    cancel_active_tasks()
                    await fsm.transition_to(AgentState.LISTENING)

                    # ⚠️ Critical: Tell the ESP32 to drop its local playback queue instantly [126]
                    await websocket.send_json({"event": "INTERRUPT"})

                    audio_buffer.clear()
                    silent_frames_count = 0
                    continue  # Skip processing this frame for STT, wait for clean audio

                # ==========================================
                # AUDIO ACCUMULATION: [IDLE] -> [LISTENING]
                # ==========================================
                if speech_prob > settings.VAD_THRESHOLD:
                    if fsm.current_state == AgentState.IDLE:
                        await fsm.transition_to(AgentState.LISTENING)
                        await websocket.send_json(
                            {"event": "STATE_CHANGE", "state": "LISTENING"}
                        )

                    audio_buffer.extend(frame_bytes)
                    silent_frames_count = 0

                elif fsm.current_state == AgentState.LISTENING:
                    audio_buffer.extend(frame_bytes)
                    silent_frames_count += 1

                    # ==========================================
                    # SILENCE TIMEOUT: [LISTENING] -> [THINKING]
                    # ==========================================
                    if silent_frames_count >= max_silent_frames:
                        await fsm.transition_to(AgentState.PROCESSING)
                        await websocket.send_json(
                            {"event": "STATE_CHANGE", "state": "THINKING"}
                        )

                        # Extract audio safely before clearing
                        final_audio_bytes = bytes(audio_buffer)
                        audio_buffer.clear()
                        silent_frames_count = 0

                        # ==========================================
                        # BACKGROUND TASK: [THINKING] -> [SPEAKING]
                        # ==========================================
                        # CRITICAL FIX (B023): Bind audio_data to local scope instantly 
                        # to prevent the while loop from overwriting it on the next frame.
                        async def process_and_speak(audio_data=final_audio_bytes):
                            try:
                                # 1. STT (Whisper.cpp / Parakeet) [24, 61]
                                user_prompt = await audio_pipeline.transcribe(audio_data)
                                if not user_prompt.strip():
                                    await fsm.transition_to(AgentState.IDLE)
                                    await websocket.send_json(
                                        {"event": "STATE_CHANGE", "state": "IDLE"}
                                    )
                                    return

                                logger.info(f"User: {user_prompt}")
                                await websocket.send_json(
                                    {"event": "TRANSCRIPT", "text": user_prompt}
                                )

                                # 2. LLM (Qwen2.5-7B + SQLite RAG tools) [46, 38]
                                ai_response = await llm.query(user_prompt)
                                logger.info(f"AI: {ai_response}")

                                await fsm.transition_to(AgentState.SPEAKING)
                                await websocket.send_json(
                                    {"event": "STATE_CHANGE", "state": "SPEAKING"}
                                )

                                # 3. TTS (Kokoro-82M) [32]
                                pcm_audio_out = await audio_pipeline.synthesize_speech(ai_response)

                                # Stream audio back in safe chunks
                                chunk_size = 4096
                                for i in range(0, len(pcm_audio_out), chunk_size):
                                    if fsm.current_state != AgentState.SPEAKING:
                                        break  # Barge-in killed the loop

                                    await websocket.send_bytes(
                                        pcm_audio_out[i : i + chunk_size]
                                    )
                                    # Simulate hardware consumption rate (16kHz 16-bit Mono)
                                    await asyncio.sleep(0.125)

                                if fsm.current_state == AgentState.SPEAKING:
                                    await fsm.transition_to(AgentState.IDLE)
                                    await websocket.send_json(
                                        {"event": "STATE_CHANGE", "state": "IDLE"}
                                    )

                            except asyncio.CancelledError:
                                logger.info("Background processing cancelled by barge-in.")
                                # Do not transition state here; barge-in logic already handled it
                            except Exception as e:
                                logger.error(f"Processing Error: {e}")
                                await fsm.transition_to(AgentState.ERROR)

                        # Track the task so we can kill it on barge-in [286]
                        task = asyncio.create_task(process_and_speak())
                        active_tasks.add(task)
                        task.add_done_callback(active_tasks.discard)

    except WebSocketDisconnect:
        logger.info("ESP32-S3-BOX-3B disconnected.")
    except Exception as e:
        logger.error(f"WebSocket Fatal Error: {e}")
    finally:
        cancel_active_tasks()
        fsm.reset()