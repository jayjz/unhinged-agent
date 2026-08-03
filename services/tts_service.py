# services/tts_service.py
import httpx
from loguru import logger

class TTSService:
    def __init__(self, endpoint: str = "http://localhost:8880"):
        self.endpoint = endpoint
        self.default_voice = "af_heart"
        logger.info(f"Local TTS Service initialized. Pointing to {self.endpoint}")

    async def synthesize_speech(self, text: str, voice: str = None) -> bytes:
        """
        Hits the local Kokoro FastAPI container, retrieves the WAV audio,
        strips the header, and returns raw PCM bytes for WebSocket streaming.
        """
        target_voice = voice or self.default_voice
        url = f"{self.endpoint}/v1/audio/speech"
        
        payload = {
            "input": text,
            "voice": target_voice,
            "response_format": "wav",
            "speed": 1.0
        }

        try:
            # Using httpx for async HTTP requests (replace aiohttp/requests)
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=15.0)
                response.raise_for_status()
                
                wav_bytes = response.content
                
                # Strip the 44-byte WAV header to get raw PCM data for the ESP32
                if wav_bytes.startswith(b'RIFF'):
                    logger.debug("Stripping WAV header for raw PCM stream.")
                    return wav_bytes[44:]
                
                return wav_bytes

        except httpx.ConnectError:
            logger.error("Failed to connect to Kokoro TTS. Is the Docker container running on port 8880?")
            raise
        except Exception as e:
            logger.error(f"TTS Synthesis failed: {e}")
            raise