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

# Global singletons — loaded ONCE for the entire process (8GB VRAM budget)
audio_pipeline = None
llm_service = None
esphome_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global audio_pipeline, llm_service, esphome_task
    logger.info("Booting Unhinged Agent Host...")

    init_db()

    # Load models exactly once. Never construct these inside ESPHomeBridge.
    audio_pipeline = AudioPipelineService()
    llm_service = LLMService()
    logger.info(
        "Core services loaded once (STT device={}, model={}). VRAM budget protected.",
        settings.stt_device,
        settings.stt_model_size,
    )

    bridge = ESPHomeBridge(
        edge_ip=settings.esphome_edge_ip,
        password=settings.esphome_password,
        audio_pipeline=audio_pipeline,
        llm=llm_service,
    )
    esphome_task = asyncio.create_task(bridge.connect_and_listen())

    yield

    logger.info("Shutting down host...")
    if esphome_task:
        esphome_task.cancel()
        try:
            await esphome_task
        except asyncio.CancelledError:
            pass
    if llm_service:
        await llm_service.close()


app = FastAPI(
    title="Unhinged Agent Host",
    version="0.2.1",
    lifespan=lifespan,
)

app.include_router(websocket_router)


@app.get("/health")
async def health_check():
    return {
        "status": "online",
        "mode": "hybrid-edge",
        "edge_ip": settings.esphome_edge_ip,
        "stt_device": settings.stt_device,
        "stt_model": settings.stt_model_size,
        "models_loaded": audio_pipeline is not None and llm_service is not None,
    }
