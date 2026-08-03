from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger

# Import global settings
from config.settings import settings

# Global singletons
audio_pipeline = None
llm_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global audio_pipeline, llm_service
    logger.info("🚀 Booting Unhinged Agent Host...")
    
    # We will instantiate AudioPipelineService and LLMService here 
    # to load models ONCE into the RTX 4060 VRAM, protecting the 8GB limit.
    
    logger.info("✅ Core services loaded.")
    yield
    
    logger.info("🛑 Shutting down host and releasing VRAM...")

app = FastAPI(
    title="Unhinged Agent Host",
    version="0.1.0",
    lifespan=lifespan
)

# We will mount the WebSocket router after the lifespan context is verified
@app.get("/health")
async def health_check():
    return {"status": "online", "mode": "hybrid-edge"}