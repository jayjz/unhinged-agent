import asyncio
from loguru import logger
from aioesphomeapi import APIClient, VoiceAssistantEventType, VoiceAssistantAudio

# Import our hardened, hardware-agnostic services
from services.audio_pipeline import AudioPipelineService
from services.llm_service import LLMService
from core.fsm import AgentState, StateMachine
from config.settings import settings

class ESPHomeBridge:
    def __init__(self, edge_ip: str, password: str = ""):
        self.ip = edge_ip
        self.client = APIClient(
            address=edge_ip,
            port=6053,
            password=password,
            noise_psk=None # Set to your noise_psk if you enabled encryption in ESPHome
        )
        self.fsm = StateMachine()
        self.audio_pipeline = AudioPipelineService()
        self.llm = LLMService()
        self._current_audio_buffer = bytearray()
        self._processing_task = None

    async def _on_voice_event(self, event_type: VoiceAssistantEventType, data: dict):
        """Maps ESPHome hardware events to our internal FSM and pipeline."""
        
        if event_type == VoiceAssistantEventType.VOICE_ASSISTANT_RUN_START:
            logger.info("🎤 Wake word detected by ESP32! Starting listen cycle.")
            self._current_audio_buffer.clear()
            await self.fsm.transition_to(AgentState.LISTENING)
            
        elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_STT_END:
            logger.info("🛑 ESPHome VAD signaled end of speech. Processing...")
            await self.fsm.transition_to(AgentState.PROCESSING)
            
            # Cancel any previous processing task if the user rapidly interrupted
            if self._processing_task and not self._processing_task.done():
                self._processing_task.cancel()
                
            # Start the heavy pipeline in the background
            self._processing_task = asyncio.create_task(self._process_audio_turn())

        elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_ERROR:
            logger.error(f"❌ ESP32 reported an audio pipeline error: {data.get('code')} - {data.get('message')}")
            await self.fsm.transition_to(AgentState.ERROR)
            self._current_audio_buffer.clear()

        elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_TTS_STREAM_START:
            logger.info("🔊 ESPHome is ready to receive TTS audio.")
            await self.fsm.transition_to(AgentState.SPEAKING)

        elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_TTS_STREAM_END:
            logger.info("✅ TTS stream complete. Returning to IDLE.")
            await self.fsm.transition_to(AgentState.IDLE)

    async def _on_voice_audio(self, audio: VoiceAssistantAudio):
        """Receives 16kHz 16-bit Mono PCM chunks directly from the ESP32."""
        if self.fsm.current_state == AgentState.LISTENING and audio.data:
            self._current_audio_buffer.extend(audio.data)

    async def _process_audio_turn(self):
        """The core brain: STT -> LLM -> TTS -> Stream back to ESP32."""
        try:
            # 1. Speech to Text
            pcm_data = bytes(self._current_audio_buffer)
            if not pcm_data:
                logger.warning("Empty audio buffer received.")
                return

            user_prompt = await self.audio_pipeline.transcribe(pcm_data)
            logger.info(f"📝 STT Transcript: '{user_prompt}'")
            
            if not user_prompt.strip():
                logger.info("Silence detected, aborting turn.")
                return

            # 2. LLM Processing (includes tool calling)
            ai_response = await self.llm.query(user_prompt)
            logger.info(f"🧠 LLM Response: '{ai_response}'")

            # 3. Text to Speech Synthesis (returns 16kHz 16-bit Mono PCM)
            pcm_audio_out = await self.audio_pipeline.synthesize_speech(ai_response)
            
            # 4. Stream TTS back to ESPHome in chunks
            chunk_size = 1024 # ESPHome handles 1024-byte chunks well
            for i in range(0, len(pcm_audio_out), chunk_size):
                chunk = pcm_audio_out[i:i + chunk_size]
                is_end = (i + chunk_size) >= len(pcm_audio_out)
                
                # Send audio chunk to ESP32
                await self.client.voice_assistant_send_audio(
                    VoiceAssistantAudio(data=chunk, end=is_end)
                )
                
                # Tiny yield to prevent blocking the event loop
                await asyncio.sleep(0.01)

        except asyncio.CancelledError:
            logger.info("🛑 Processing task cancelled (likely due to barge-in).")
        except Exception as e:
            logger.error(f"💥 Pipeline processing failed: {e}", exc_info=True)
            await self.fsm.transition_to(AgentState.ERROR)

    async def connect_and_listen(self):
        """Establishes the Native API bridge to the BOX-3B."""
        logger.info(f"🔗 Connecting to ESP32-S3-BOX-3B at {self.ip}...")
        
        try:
            await self.client.connect(login=True)
            logger.info("✅ Connected successfully. Subscribing to voice events...")
            
            # Subscribe to the hardware's audio stream and events
            await self.client.subscribe_voice_assistant(
                on_event=self._on_voice_event,
                on_audio=self._on_voice_audio
            )
            
            # Keep the connection alive
            while True:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Connection to ESP32 failed: {e}")
        finally:
            await self.client.disconnect()
            await self.llm.close()