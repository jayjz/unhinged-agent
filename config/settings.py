from pydantic import Field, PositiveFloat, PositiveInt, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Audio / VAD
    SAMPLE_RATE: PositiveInt = 16_000
    VAD_FRAME_SAMPLES: PositiveInt = 512
    VAD_THRESHOLD: float = Field(default=0.5, ge=0.0, le=1.0)
    SILENCE_DURATION_MS: PositiveInt = 1_000
    MAX_AUDIO_BUFFER_SECONDS: PositiveFloat = 30.0

    # STT
    STT_MODEL_SIZE: str = "base.en"
    STT_DEVICE: str = "cuda"
    STT_COMPUTE_TYPE: str = "float16"
    STT_MAX_WORKERS: PositiveInt = 1

    # LLM
    OLLAMA_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "unhinged-qwen"
    LLM_REQUEST_TIMEOUT_SECONDS: PositiveFloat = 60.0
    LLM_MAX_TOOL_ROUNDS: PositiveInt = 4
    LLM_HISTORY_MESSAGES: PositiveInt = 16

    # TTS (HTTP sidecar)
    TTS_URL: str = "http://localhost:8880"
    TTS_DEFAULT_VOICE: str = "af_heart"
    TTS_TIMEOUT_SECONDS: PositiveFloat = 30.0
    MAX_TTS_RESPONSE_BYTES: PositiveInt = 20 * 1024 * 1024

    # WebSocket / safety bounds
    MAX_WEBSOCKET_MESSAGE_BYTES: PositiveInt = 64 * 1024
    MAX_NETWORK_BUFFER_BYTES: PositiveInt = 128 * 1024
    MAX_CONCURRENT_CONNECTIONS: PositiveInt = 4
    WEBSOCKET_TOKEN: SecretStr | None = None
    OUTBOUND_AUDIO_CHUNK_BYTES: PositiveInt = 4_096

    @field_validator("WEBSOCKET_TOKEN", mode="before")
    @classmethod
    def empty_token_is_unset(cls, value: object) -> object:
        return None if value == "" else value

    @property
    def vad_frame_size_bytes(self) -> int:
        return self.VAD_FRAME_SAMPLES * 2  # PCM16 mono

    @property
    def max_audio_buffer_bytes(self) -> int:
        return int(self.MAX_AUDIO_BUFFER_SECONDS * self.SAMPLE_RATE * 2)


settings = Settings()
