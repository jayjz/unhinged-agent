# services/audio_pipeline.py
import asyncio
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import torch
from faster_whisper import WhisperModel
from loguru import logger

from config.settings import settings
from services.tts_service import TTSService  # Our new 100% local Kokoro API wrapper


class AudioPipelineService:
    def __init__(self):
        # Isolate blocking CPU work to avoid locking the FastAPI event loop
        self.stt_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="STT")
        
        logger.info("Loading Silero VAD model for frame gating...")
        # Silero VAD is lightweight enough to run comfortably on CPU [18]
        self.vad_model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            onnx=True,
        )

        # ⚠️ VRAM BUDGET ENFORCEMENT: Keep STT_MODEL_SIZE to "tiny.en" or "base.en"
        # This consumes ~500MB, leaving ~6.5GB for Qwen2.5-7B and Kokoro on your 8GB RTX 4060.
        logger.info(f"Loading Faster-Whisper ({settings.STT_MODEL_SIZE}) on {settings.STT_DEVICE}...")
        self.stt_model = WhisperModel(
            settings.STT_MODEL_SIZE, 
            device=settings.STT_DEVICE,
            compute_type=settings.STT_COMPUTE_TYPE,
        )

        logger.info("Initializing Local Kokoro TTS Service...")
        self.tts = TTSService()

    def is_speech(self, audio_chunk: np.ndarray) -> float:
        """
        VAD Gate: Evaluates 512-sample frames. 
        Used during [IDLE] -> [LISTENING] transitions and barge-in detection.
        """
        tensor_chunk = torch.from_numpy(audio_chunk).float().unsqueeze(0)
        return self.vad_model(tensor_chunk, settings.SAMPLE_RATE).item()

    async def transcribe(self, pcm_data: bytes) -> str:
        """
        Offloads synchronous STT inference to a background thread.
        Triggered when transitioning from [LISTENING] -> [THINKING].
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self.stt_executor, self._sync_transcribe, pcm_data
        )

    def _sync_transcribe(self, pcm_data: bytes) -> str:
        """Converts raw PCM to numpy float32 and runs Whisper inference."""
        audio_np = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = self.stt_model.transcribe(audio_np, beam_size=1, language="en")
        return " ".join([segment.text for segment in segments]).strip()

    async def synthesize_speech(self, text: str) -> bytes:
        """
        Delegates to the local Kokoro-82M container.
        Returns raw PCM bytes ready for immediate WebSocket streaming during [SPEAKING].
        """
        return await self.tts.synthesize_speech(text)