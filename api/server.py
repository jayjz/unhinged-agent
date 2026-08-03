import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger

from config.settings import settings
from api.websocket import router as websocket_router
from services.audio_pipeline import AudioPipelineService
from services.llm_service import LLMService

# Global singletons
audio_pipeline = None
llm_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global audio_pipeline, llm_service
    logger.info("🚀 Booting Unhinged Agent Host...")
    
    # Instantiate services here to load models ONCE into the RTX 4060 VRAM
    audio_pipeline = AudioPipelineService()
    llm_service = LLMService()
    
    logger.info("✅ Core services loaded. 8GB VRAM limit protected.")
    yield
    
    logger.info("🛑 Shutting down host and releasing VRAM...")
    if llm_service:
        await llm_service.close()

app = FastAPI(
    title="Unhinged Agent Host",
    version="0.1.0",
    lifespan=lifespan
)

app.include_router(websocket_router)

@app.get("/health")
async def health_check():
    return {"status": "online", "mode": "hybrid-edge"}