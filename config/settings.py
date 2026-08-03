from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Authentication ---
    websocket_token: str = Field(default="dev_token_123", description="Required token for /ws/agent connection")

    # --- Hard Bounds (DoS & OOM Prevention) ---
    max_connections: int = Field(default=5, description="Max concurrent WebSocket connections")
    max_message_size_bytes: int = Field(default=1048576, description="1MB max WebSocket message size")
    max_utterance_seconds: int = Field(default=30, description="Max audio duration to process per turn")
    max_tts_response_bytes: int = Field(default=524288, description="512KB max TTS payload to edge")
    max_tool_rounds: int = Field(default=3, description="Max consecutive tools before forcing text")

    # --- Service Endpoints ---
    ollama_url: str = Field(default="http://127.0.0.1:11434")
    ollama_model: str = Field(default="unhinged-qwen")
    tts_endpoint: str = Field(default="http://127.0.0.1:8880") 

    # --- Audio Pipeline ---
    audio_sample_rate: int = Field(default=16000)
    audio_frame_size: int = Field(default=512) 
    
    # --- Model Configs ---
    stt_model_size: str = Field(default="base.en")
    stt_device: str = Field(default="cuda")
    stt_compute_type: str = Field(default="float16")
    vad_threshold: float = Field(default=0.5)
    silence_duration_ms: int = Field(default=1000)

    @field_validator("websocket_token")
    @classmethod
    def token_must_not_be_empty(cls, v: str) -> str:
        if not v or len(v.strip()) < 8:
            raise ValueError("websocket_token must be at least 8 characters")
        return v.strip()

settings = Settings()
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Authentication ---
    websocket_token: str = Field(default="dev_token_123", description="Required token for /ws/agent connection")

    # --- Hard Bounds (DoS & OOM Prevention) ---
    max_connections: int = Field(default=5, description="Max concurrent WebSocket connections")
    max_message_size_bytes: int = Field(default=1048576, description="1MB max WebSocket message size")
    max_utterance_seconds: int = Field(default=30, description="Max audio duration to process per turn")
    max_tts_response_bytes: int = Field(default=524288, description="512KB max TTS payload to edge")
    max_tool_rounds: int = Field(default=3, description="Max consecutive tools before forcing text")

    # --- Service Endpoints ---
    ollama_url: str = Field(default="http://127.0.0.1:11434")
    ollama_model: str = Field(default="unhinged-qwen")
    tts_endpoint: str = Field(default="http://127.0.0.1:8880") 

    # --- Audio Pipeline ---
    audio_sample_rate: int = Field(default=16000)
    audio_frame_size: int = Field(default=512) 
    
    # --- Model Configs ---
    stt_model_size: str = Field(default="base.en")
    stt_device: str = Field(default="cuda")
    stt_compute_type: str = Field(default="float16")
    vad_threshold: float = Field(default=0.5)
    silence_duration_ms: int = Field(default=1000)

    @field_validator("websocket_token")
    @classmethod
    def token_must_not_be_empty(cls, v: str) -> str:
        if not v or len(v.strip()) < 8:
            raise ValueError("websocket_token must be at least 8 characters")
        return v.strip()

settings = Settings()