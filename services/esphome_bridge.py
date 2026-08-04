import asyncio
from loguru import logger
from aioesphomeapi import APIClient, VoiceAssistantEventType

from services.audio_pipeline import AudioPipelineService
from services.llm_service import LLMService
from core.fsm import AgentState, StateMachine, InvalidTransition
from config.settings import settings


class ESPHomeBridge:
    """Edge bridge. Requires host-owned audio_pipeline + llm (no second GPU load)."""

    def __init__(
        self,
        edge_ip: str,
        audio_pipeline: AudioPipelineService,
        llm: LLMService,
        password: str = "",
    ):
        if audio_pipeline is None or llm is None:
            raise ValueError(
                "ESPHomeBridge requires shared audio_pipeline and llm from host lifespan. "
                "Do not construct models inside the bridge — that double-loads VRAM."
            )

        self.ip = edge_ip
        self.client = APIClient(
            address=edge_ip,
            port=6053,
            password=password,
            noise_psk=None,
        )
        self.fsm = StateMachine()
        self.audio_pipeline = audio_pipeline
        self.llm = llm
        self._current_audio_buffer = bytearray()
        self._processing_task = None
        # Hard cap utterance size (16-bit mono @ sample rate) to protect host RAM
        self._max_buffer_bytes = settings.max_utterance_seconds * settings.audio_sample_rate * 2

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
            remaining = self._max_buffer_bytes - len(self._current_audio_buffer)
            if remaining <= 0:
                return
            if len(data) > remaining:
                data = data[:remaining]
            self._current_audio_buffer.extend(data)

    async def _process_audio_turn(self):
        """STT -> LLM -> TTS -> stream back to ESP32 (shared host models only)."""
        try:
            pcm_data = bytes(self._current_audio_buffer)
            self._current_audio_buffer.clear()

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

            # Cap outbound TTS size to protect edge TCP buffer
            max_out = settings.max_tts_response_bytes
            if len(pcm_audio_out) > max_out:
                logger.warning(
                    "TTS output truncated from {} to {} bytes",
                    len(pcm_audio_out),
                    max_out,
                )
                pcm_audio_out = pcm_audio_out[:max_out]

            chunk_size = 1024
            for i in range(0, len(pcm_audio_out), chunk_size):
                chunk = pcm_audio_out[i : i + chunk_size]
                await self.client.send_voice_assistant_audio(chunk)
                # ~32 ms pacing (512 samples / 16000 Hz) — do not remove
                await asyncio.sleep(0.03)

            await self.client.send_voice_assistant_audio(b"")

        except asyncio.CancelledError:
            logger.info("Processing task cancelled (barge-in).")
            raise
        except Exception as e:
            logger.error("Pipeline processing failed: {}", e, exc_info=True)
            await self._safe_transition(AgentState.ERROR)

    async def connect_and_listen(self):
        """Native API bridge with auto-reconnect. Does not load models."""
        while True:
            logger.info("Attempting to connect to ESP32-S3-BOX-3B at {}...", self.ip)
            try:
                await self.client.connect(login=True)
                logger.info("Connected successfully. Subscribing to voice events...")

                await self.client.subscribe_voice_assistant(
                    self._on_voice_event,
                    self._on_voice_audio,
                )

                while True:
                    await asyncio.sleep(1)

            except Exception as e:
                logger.warning(
                    "Connection to ESP32 failed or dropped: {}. Retrying in 5 seconds...",
                    e,
                )
                await asyncio.sleep(5)
