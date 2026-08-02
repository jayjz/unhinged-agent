import asyncio
import subprocess
from concurrent.futures import ThreadPoolExecutor

import edge_tts
from faster_whisper import WhisperModel
from loguru import logger
import numpy as np
import torch

from config.settings import settings


class AudioPipelineService:

    def __init__(self):
        self.stt_executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="STT"
        )
        self.audio_conversion_executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="AudioConv"
        )

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

        logger.info(
            "TTS Engine: edge-tts initialized (Microsoft Azure Neural Voices)"
        )
        self.tts_voice = (
            "en-US-GuyNeural"  # Excellent, natural, low-latency male voice
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
        audio_np = (
            np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32)
            / 32768.0
        )
        segments, _ = self.stt_model.transcribe(
            audio_np, beam_size=1, language="en"
        )
        return " ".join([segment.text for segment in segments]).strip()

    async def synthesize_speech(
        self, text: str, voice: str | None = None
    ) -> bytes:
        """Uses edge-tts to generate MP3 audio, then uses FFmpeg to convert it

        to raw 16kHz 16-bit PCM for the WebSocket stream.
        """
        communicate = edge_tts.Communicate(text, self.tts_voice)
        mp3_data = bytearray()

        # Collect the MP3 stream asynchronously
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_data.extend(chunk["data"])

        # Offload the synchronous FFmpeg conversion to a thread
        loop = asyncio.get_running_loop()
        pcm_data = await loop.run_in_executor(
            self.audio_conversion_executor,
            self._convert_mp3_to_pcm,
            bytes(mp3_data),
        )
        return pcm_data

    def _convert_mp3_to_pcm(self, mp3_bytes: bytes) -> bytes:
        """Uses an FFmpeg subprocess to convert MP3 bytes to raw PCM.

        Requires FFmpeg to be installed on the system PATH.
        """
        process = subprocess.Popen(
            [
                "ffmpeg",
                "-i",
                "pipe:0",
                "-f",
                "s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                "pipe:1",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        pcm_data, _ = process.communicate(input=mp3_bytes)
        return pcm_data