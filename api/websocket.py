import asyncio

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from config.settings import settings
from core.fsm import AgentState, StateMachine
from services.audio_pipeline import AudioPipelineService
from services.llm_service import LLMService  # Assuming you built this

router = APIRouter()


@router.websocket("/ws/agent")
async def websocket_agent_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected via WebSocket.")

    fsm = StateMachine()
    audio_pipeline = AudioPipelineService()
    llm = LLMService()

    audio_buffer = bytearray()
    silent_frames_count = 0
    max_silent_frames = int(
        (settings.SILENCE_DURATION_MS / 1000.0)
        / (settings.CHUNK_SIZE / settings.SAMPLE_RATE)
    )

    # Track background tasks so we can cancel them on barge-in
    active_llm_task = None
    active_tts_task = None

    try:
        while True:
            data = await websocket.receive_bytes()
            frame_np = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0

            if len(frame_np) != settings.CHUNK_SIZE:
                continue

            speech_prob = audio_pipeline.is_speech(frame_np)

            # BARGE-IN CHECK
            if (
                fsm.current_state in (AgentState.SPEAKING, AgentState.PROCESSING)
                and speech_prob > settings.VAD_THRESHOLD
            ):
                logger.warning("Barge-in detected! Cancelling background tasks.")

                # Cancel LLM if it's still thinking
                if active_llm_task and not active_llm_task.done():
                    active_llm_task.cancel()

                # Cancel TTS if it's still generating
                if active_tts_task and not active_tts_task.done():
                    active_tts_task.cancel()

                await fsm.transition_to(AgentState.LISTENING)
                await websocket.send_json({"event": "INTERRUPT"})
                audio_buffer.clear()
                silent_frames_count = 0
                continue  # Skip processing this frame, wait for next

            # State: LISTENING
            if speech_prob > settings.VAD_THRESHOLD:
                if fsm.current_state == AgentState.IDLE:
                    await fsm.transition_to(AgentState.LISTENING)
                    await websocket.send_json(
                        {"event": "STATE_CHANGE", "state": "LISTENING"}
                    )

                audio_buffer.extend(data)
                silent_frames_count = 0

            elif fsm.current_state == AgentState.LISTENING:
                audio_buffer.extend(data)
                silent_frames_count += 1

                if silent_frames_count >= max_silent_frames:
                    await fsm.transition_to(AgentState.PROCESSING)
                    await websocket.send_json(
                        {"event": "STATE_CHANGE", "state": "THINKING"}
                    )

                    user_prompt = await audio_pipeline.transcribe(bytes(audio_buffer))
                    audio_buffer.clear()
                    silent_frames_count = 0

                    if not user_prompt.strip():
                        await fsm.transition_to(AgentState.IDLE)
                        await websocket.send_json(
                            {"event": "STATE_CHANGE", "state": "IDLE"}
                        )
                        continue

                    logger.info(f"User Said: {user_prompt}")
                    await websocket.send_json(
                        {"event": "TRANSCRIPT", "text": user_prompt}
                    )

                    # Wrap LLM in a task so it can be cancelled
                    async def run_llm():
                        return await llm.query(user_prompt)

                    active_llm_task = asyncio.create_task(run_llm())
                    ai_response = await active_llm_task

                    logger.info(f"AI Response: {ai_response}")
                    await fsm.transition_to(AgentState.SPEAKING)
                    await websocket.send_json(
                        {"event": "STATE_CHANGE", "state": "SPEAKING"}
                    )

                    # Wrap TTS in a task so it can be cancelled
                    async def run_tts():
                        return await audio_pipeline.synthesize_speech(ai_response)

                    active_tts_task = asyncio.create_task(run_tts())
                    pcm_audio_out = await active_tts_task

                    # Stream audio
                    chunk_size = 4096
                    for i in range(0, len(pcm_audio_out), chunk_size):
                        if fsm.current_state != AgentState.SPEAKING:
                            break  # Barge-in broke the loop
                        await websocket.send_bytes(pcm_audio_out[i : i + chunk_size])
                        # Calculate exact sleep time for 16kHz 16-bit mono:
                        # 4096 bytes = 2048 samples. 2048 / 16000 = 0.128 seconds.
                        await asyncio.sleep(0.125)

                    if fsm.current_state == AgentState.SPEAKING:
                        await fsm.transition_to(AgentState.IDLE)
                        await websocket.send_json(
                            {"event": "STATE_CHANGE", "state": "IDLE"}
                        )

    except asyncio.CancelledError:
        logger.info("WebSocket connection cancelled.")
    except WebSocketDisconnect:
        logger.info("Client disconnected.")
    except Exception as e:
        logger.error(f"WebSocket Error: {e}")
        await fsm.transition_to(AgentState.ERROR)
