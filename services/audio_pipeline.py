import asyncio
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import torch
from scipy.signal import resample_poly
from faster_whisper import WhisperModel
from kokoro_onnx import Kokoro
from loguru import logger

from config.settings import settings

class AudioPipelineService:
    def __init__(self):
        self.stt_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="STT")
        self.tts_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="TTS")

        logger.info("Loading Silero VAD model into CPU/RAM...")
        self.vad_model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            onnx=True,
        )

        logger.info(f"Loading Faster-Whisper ({settings.stt_model_size}) to {settings.stt_device}...")
        self.stt_model = WhisperModel(
            settings.stt_model_size,
            device=settings.stt_device,
            compute_type=settings.stt_compute_type,
        )

        logger.info("Initializing Native Kokoro-82M TTS (CPU) to preserve GPU VRAM...")
        try:
            self.tts_model = Kokoro(
                model_path="weights/kokoro-v0_19.onnx",
                voices_path="weights/voices.bin"
            )
        except Exception as e:
            logger.error(f"Failed to load Kokoro TTS weights. Error: {e}")
            self.tts_model = None

    def is_speech(self, audio_chunk: np.ndarray) -> float:
        tensor_chunk = torch.from_numpy(audio_chunk).float().unsqueeze(0)
        return self.vad_model(tensor_chunk, settings.audio_sample_rate).item()

    async def transcribe(self, pcm_data: bytes) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.stt_executor, self._sync_transcribe, pcm_data)

    def _sync_transcribe(self, pcm_data: bytes) -> str:
        audio_np = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = self.stt_model.transcribe(audio_np, beam_size=1, language="en")
        return " ".join([segment.text for segment in segments]).strip()

    async def synthesize_speech(self, text: str, voice: str = "af_heart") -> bytes:
        if not text.strip() or not self.tts_model:
            return b""
            
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.tts_executor, self._sync_synthesize, text, voice)

    def _sync_synthesize(self, text: str, voice: str) -> bytes:
        try:
            # Kokoro returns float32 numpy array in [-1.0, 1.0] range at 24kHz
            samples, sample_rate = self.tts_model.create(text, voice=voice, speed=1.0)
            
            # Scipy polyphase resampling (24kHz to 16kHz -> 2:3 ratio)
            # This avoids FFT ringing artifacts and is significantly faster on the CPU
            resampled = resample_poly(samples, 2, 3)
            
            # Clip to prevent integer overflow, then cast to 16-bit PCM
            pcm_samples = np.clip(resampled, -1.0, 1.0)
            return (pcm_samples * 32767).astype(np.int16).tobytes()
        except Exception as e:
            logger.error(f"Native TTS Synthesis failed: {e}")
            return b""