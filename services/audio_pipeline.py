import asyncio
from concurrent.futures import ThreadPoolExecutor

import aiohttp
import numpy as np
import torch
from faster_whisper import WhisperModel
from loguru import logger

from config.settings import settings


class AudioPipelineService:
    def __init__(self):
        # We only need one executor now since TTS is handled via async HTTP
        self.stt_executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="STT"
        )

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

        logger.info(f"TTS Engine: Local Kokoro-82M via {settings.tts_endpoint}")

    def is_speech(self, audio_chunk: np.ndarray) -> float:
        """Runs Silero VAD on a 16kHz audio frame."""
        tensor_chunk = torch.from_numpy(audio_chunk).float().unsqueeze(0)
        return self.vad_model(tensor_chunk, settings.audio_sample_rate).item()

    async def transcribe(self, pcm_data: bytes) -> str:
        """Offloads synchronous Faster-Whisper transcription to a thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self.stt_executor, self._sync_transcribe, pcm_data
        )

    def _sync_transcribe(self, pcm_data: bytes) -> str:
        audio_np = (
            np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32)
            / 32768.0
        )
        segments, _ = self.stt_model.transcribe(
            audio_np, beam_size=1, language="en"
        )
        return " ".join([segment.text for segment in segments]).strip()

    async def synthesize_speech(self, text: str, voice: str = "af_heart") -> bytes:
        """
        Calls the local Kokoro-FastAPI container asynchronously.
        Expects a 16kHz 16-bit Mono WAV or PCM payload in return.
        """
        if not text.strip():
            return b""
            
        url = f"{settings.tts_endpoint}/v1/audio/speech"
        payload = {
            "input": text,
            "voice": voice,
            "response_format": "wav" 
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10.0) as response:
                    if response.status != 200:
                        logger.error(f"Local TTS Sidecar Error: HTTP {response.status}")
                        return b""
                    
                    audio_bytes = await response.read()
                    
                    # Enforce the edge contract: Strip 44-byte WAV RIFF header to yield raw PCM
                    if audio_bytes.startswith(b'RIFF'):
                        return audio_bytes[44:]
                        
                    return audio_bytes
                    
        except Exception as e:
            logger.error(f"Failed to connect to local TTS sidecar: {e}")
            return b""