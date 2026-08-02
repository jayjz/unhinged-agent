import asyncio
import io
import wave
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import torch
from faster_whisper import WhisperModel
from loguru import logger
from piper import PiperVoice
from piper.download import download_voice, get_voices

from config.settings import settings


class AudioPipelineService:
    def __init__(self):
        self.stt_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="STT")
        self.tts_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="TTS")

        logger.info("Loading Silero VAD model...")
        self.vad_model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            onnx=True,
        )

        logger.info(f"Loading Faster-Whisper ({settings.STT_MODEL_SIZE})...")
        self.stt_model = WhisperModel(
            settings.STT_MODEL_SIZE,
            device=settings.STT_DEVICE,
            compute_type=settings.STT_COMPUTE_TYPE,
        )

        # --- PIPER TTS INITIALIZATION ---
        logger.info("Initializing Piper TTS...")
        self.voice_name = "en_US-lessac-medium"  # High quality, fast

        # Piper handles downloading the model and config automatically if missing
        voices = get_voices()
        if self.voice_name not in voices:
            logger.info(f"Downloading Piper voice: {self.voice_name}...")
            download_voice(self.voice_name, "./weights/piper")

        model_path, config_path = voices[self.voice_name]
        self.tts_model = PiperVoice.load(
            model_path,
            config_path=config_path,
            use_cuda=(settings.STT_DEVICE == "cuda"),
        )

    def is_speech(self, audio_chunk: np.ndarray) -> float:
        tensor_chunk = torch.from_numpy(audio_chunk).float().unsqueeze(0)
        return self.vad_model(tensor_chunk, settings.SAMPLE_RATE).item()

    async def transcribe(self, pcm_data: bytes) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self.stt_executor, self._sync_transcribe, pcm_data
        )

    def _sync_transcribe(self, pcm_data: bytes) -> str:
        audio_np = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = self.stt_model.transcribe(audio_np, beam_size=1, language="en")
        return " ".join([segment.text for segment in segments]).strip()

    async def synthesize_speech(self, text: str, voice: str = None) -> bytes:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self.tts_executor, self._sync_synthesize, text
        )

    def _sync_synthesize(self, text: str) -> bytes:
        # Piper synthesizes directly to a byte stream
        audio_stream = io.BytesIO()
        wav_stream = wave.open(audio_stream, "wb")
        wav_stream.setnchannels(1)
        wav_stream.setsampwidth(2)
        wav_stream.setframerate(self.tts_model.config.sample_rate)

        # Synthesize and write to the wav stream
        self.tts_model.synthesize_wav(text, wav_stream)
        wav_stream.close()

        # Extract raw PCM bytes (skip the 44-byte WAV header for our streaming protocol)
        pcm_data = audio_stream.getvalue()[44:]
        return pcm_data
