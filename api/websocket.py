import asyncio
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from loguru import logger

from config.settings import settings
from core.fsm import AgentState, StateMachine

router = APIRouter()

# Track active connections to enforce our DoS limits
active_connections = set()

@router.websocket("/ws/agent")
async def websocket_agent_endpoint(websocket: WebSocket, token: str = ""):
    # 1. Security & Connection Bounds
    if token != settings.websocket_token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return

    if len(active_connections) >= settings.max_connections:
        await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER, reason="Capacity full")
        return

    await websocket.accept()
    active_connections.add(websocket)
    logger.info(f"Client connected. Active: {len(active_connections)}/{settings.max_connections}")

    # 2. Dependency Injection: Fetch the global singletons loaded during server lifespan
    # This prevents circular imports and guarantees models are only loaded into the RTX 4060 ONCE.
    import api.server
    audio_pipeline = api.server.audio_pipeline
    llm = api.server.llm_service

    if not audio_pipeline or not llm:
        logger.error("Inference services not loaded. Is the lifespan running?")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        active_connections.remove(websocket)
        return

    # 3. State & Buffer Setup
    fsm = StateMachine()
    audio_buffer = bytearray()
    silent_frames_count = 0
    
    # Calculate limits based on the new Pydantic V2 lowercase settings
    max_silent_frames = int(
        (settings.silence_duration_ms / 1000.0)
        / (settings.audio_frame_size / settings.audio_sample_rate)
    )
    max_buffer_bytes = settings.max_utterance_seconds * settings.audio_sample_rate * 2

    # Track background tasks so we can cancel them on barge-in
    active_llm_task = None
    active_tts_task = None

    try:
        while True:
            data = await websocket.receive_bytes()
            frame_np = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0

            if len(frame_np) != settings.audio_frame_size:
                continue

            speech_prob = audio_pipeline.is_speech(frame_np)

            # BARGE-IN CHECK
            if (
                fsm.current_state in (AgentState.SPEAKING, AgentState.PROCESSING)
                and speech_prob > settings.vad_threshold
            ):
                logger.warning("Barge-in detected! Cancelling background tasks.")

                if active_llm_task and not active_llm_task.done():
                    active_llm_task.cancel()

                if active_tts_task and not active_tts_task.done():
                    active_tts_task.cancel()

                await fsm.transition_to(AgentState.LISTENING)
                await websocket.send_json({"event": "INTERRUPT"})
                audio_buffer.clear()
                silent_frames_count = 0
                continue  

            # OOM GUARD: Force processing if max utterance length is reached
            if len(audio_buffer) >= max_buffer_bytes:
                logger.warning("Max utterance length reached. Forcing STT.")
                speech_prob = 0.0 
                silent_frames_count = max_silent_frames

            # State: LISTENING
            if speech_prob > settings.vad_threshold:
                if fsm.current_state == AgentState.IDLE:
                    await fsm.transition_to(AgentState.LISTENING)
                    await websocket.send_json({"event": "STATE_CHANGE", "state": "LISTENING"})

                audio_buffer.extend(data)
                silent_frames_count = 0

            elif fsm.current_state == AgentState.LISTENING:
                audio_buffer.extend(data)
                silent_frames_count += 1

                if silent_frames_count >= max_silent_frames:
                    await fsm.transition_to(AgentState.PROCESSING)
                    await websocket.send_json({"event": "STATE_CHANGE", "state": "THINKING"})

                    user_prompt = await audio_pipeline.transcribe(bytes(audio_buffer))
                    audio_buffer.clear()
                    silent_frames_count = 0

                    if not user_prompt.strip():
                        await fsm.transition_to(AgentState.IDLE)
                        await websocket.send_json({"event": "STATE_CHANGE", "state": "IDLE"})
                        continue

                    logger.info(f"User Said: {user_prompt}")
                    await websocket.send_json({"event": "TRANSCRIPT", "text": user_prompt})

                    # Wrap LLM in a cancelable task
                    async def run_llm():
                        return await llm.query(user_prompt)

                    active_llm_task = asyncio.create_task(run_llm())
                    ai_response = await active_llm_task

                    logger.info(f"AI Response: {ai_response}")
                    await fsm.transition_to(AgentState.SPEAKING)
                    await websocket.send_json({"event": "STATE_CHANGE", "state": "SPEAKING"})

                    # Wrap TTS in a cancelable task
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
                        
                        # Yield to event loop to allow barge-in frames to be processed
                        await asyncio.sleep(0.01)

                    if fsm.current_state == AgentState.SPEAKING:
                        await fsm.transition_to(AgentState.IDLE)
                        await websocket.send_json({"event": "STATE_CHANGE", "state": "IDLE"})

    except asyncio.CancelledError:
        logger.info("WebSocket connection cancelled.")
    except WebSocketDisconnect:
        logger.info("Client disconnected cleanly.")
    except Exception as e:
        logger.error(f"WebSocket Error: {e}", exc_info=True)
        await fsm.transition_to(AgentState.ERROR)
    finally:
        active_connections.remove(websocket)
        fsm.reset()