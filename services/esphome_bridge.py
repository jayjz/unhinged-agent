import asyncio
from loguru import logger
from aioesphomeapi import APIClient, VoiceAssistantEventType

from services.audio_pipeline import AudioPipelineService
from services.llm_service import LLMService
from core.fsm import AgentState, StateMachine, InvalidTransition


class ESPHomeBridge:
    def __init__(self, edge_ip: str, password: str = ""):
        self.ip = edge_ip
        self.client = APIClient(
            address=edge_ip,
            port=6053,
            password=password,
            noise_psk=None,
        )
        self.fsm = StateMachine()
        self.audio_pipeline = AudioPipelineService()
        self.llm = LLMService()
        self._current_audio_buffer = bytearray()
        self._processing_task = None

    async def _safe_transition(self, new_state: AgentState) -> bool:
        """Transition with guard; never let InvalidTransition crash the event loop."""
        try:
            return await self.fsm.transition_to(new_state)
        except InvalidTransition as e:
            logger.warning("Ignored illegal transition: {}", e)
            return False

    async def _on_voice_event(self, event_type: VoiceAssistantEventType, data: dict):
        """Maps ESPHome hardware events to our internal FSM and pipeline."""

        if event_type == VoiceAssistantEventType.VOICE_ASSISTANT_RUN_START:
            logger.info("Wake word detected by ESP32. Starting listen cycle.")
            # Barge-in: cancel any running turn immediately
            if self._processing_task and not self._processing_task.done():
                self._processing_task.cancel()
            self._current_audio_buffer.clear()
            await self._safe_transition(AgentState.LISTENING)

        elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_STT_END:
            logger.info("ESPHome VAD signaled end of speech. Processing...")
            await self._safe_transition(AgentState.PROCESSING)

            if self._processing_task and not self._processing_task.done():
                self._processing_task.cancel()

            self._processing_task = asyncio.create_task(self._process_audio_turn())

        elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_ERROR:
            logger.error("ESP32 reported an audio pipeline error: {}", data)
            await self._safe_transition(AgentState.ERROR)
            self._current_audio_buffer.clear()

        elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_TTS_STREAM_START:
            logger.info("ESPHome is ready to receive TTS audio.")
            await self._safe_transition(AgentState.SPEAKING)

        elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_TTS_STREAM_END:
            logger.info("TTS stream complete. Returning to IDLE.")
            await self._safe_transition(AgentState.IDLE)

    async def _on_voice_audio(self, data: bytes):
        """Receives 16kHz 16-bit Mono PCM chunks directly from the ESP32."""
        if self.fsm.current_state == AgentState.LISTENING and data:
            self._current_audio_buffer.extend(data)

    async def _process_audio_turn(self):
        """The core brain: STT -> LLM -> TTS -> Stream back to ESP32."""
        try:
            pcm_data = bytes(self._current_audio_buffer)
            if not pcm_data:
                logger.warning("Empty audio buffer received.")
                await self._safe_transition(AgentState.IDLE)
                return

            user_prompt = await self.audio_pipeline.transcribe(pcm_data)
            logger.info("STT Transcript: '{}'", user_prompt)

            if not user_prompt.strip():
                logger.info("Silence detected, aborting turn.")
                await self._safe_transition(AgentState.IDLE)
                return

            ai_response = await self.llm.query(user_prompt)
            logger.info("LLM Response: '{}'", ai_response)

            pcm_audio_out = await self.audio_pipeline.synthesize_speech(ai_response)

            # Stream TTS back to ESPHome in 1024-byte chunks (512 samples @ 16-bit)
            chunk_size = 1024
            for i in range(0, len(pcm_audio_out), chunk_size):
                chunk = pcm_audio_out[i : i + chunk_size]
                await self.client.send_voice_assistant_audio(chunk)
                # ~32 ms pacing (512 samples / 16000 Hz) to avoid flooding ESP32 TCP buffer
                await asyncio.sleep(0.03)

            # Explicit end-of-stream signal so ESPHome closes the media player buffer
            # and re-engages the microphone AEC for the next wake word.
            await self.client.send_voice_assistant_audio(b"")

        except asyncio.CancelledError:
            logger.info("Processing task cancelled (barge-in).")
            raise
        except Exception as e:
            logger.error("Pipeline processing failed: {}", e, exc_info=True)
            await self._safe_transition(AgentState.ERROR)

    async def connect_and_listen(self):
        """Establishes the Native API bridge to the BOX-3B with auto-reconnect."""
        while True:
            logger.info("Attempting to connect to ESP32-S3-BOX-3B at {}...", self.ip)
            try:
                await self.client.connect(login=True)
                logger.info("Connected successfully. Subscribing to voice events...")

                await self.client.subscribe_voice_assistant(
                    self._on_voice_event,
                    self._on_voice_audio,
                )

                # Keep the connection alive
                while True:
                    await asyncio.sleep(1)

            except Exception as e:
                logger.warning(
                    "Connection to ESP32 failed or dropped: {}. Retrying in 5 seconds...",
                    e,
                )
                await asyncio.sleep(5)
