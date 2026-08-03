import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger

from config.settings import settings
from api.websocket import router as websocket_router
from services.audio_pipeline import AudioPipelineService
from services.llm_service import LLMService
from services.esphome_bridge import ESPHomeBridge
from tools.notes_db import init_db

# Global singletons
audio_pipeline = None
llm_service = None
esphome_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global audio_pipeline, llm_service, esphome_task
    logger.info("🚀 Booting Unhinged Agent Host...")
    
    # 1. Ignite the SQLite Database
    init_db()
    
    # 2. Load models ONCE into the RTX 4060 VRAM
    audio_pipeline = AudioPipelineService()
    llm_service = LLMService()
    logger.info("✅ Core services loaded. 8GB VRAM limit protected.")

    # 3. Launch the ESPHome Native API Bridge in the background
    # Note: Replace '192.168.1.100' with your ESP32's actual static IP once it boots on your network
    bridge = ESPHomeBridge(edge_ip="192.168.1.100")
    esphome_task = asyncio.create_task(bridge.connect_and_listen())
    
    yield
    
    logger.info("🛑 Shutting down host and releasing VRAM...")
    if esphome_task:
        esphome_task.cancel()
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