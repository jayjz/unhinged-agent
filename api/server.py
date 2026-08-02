from fastapi import FastAPI
from loguru import logger

from api.websocket import router as websocket_router

app = FastAPI(title="Unhinged Agent Backend")

# Bind the WebSocket endpoint
app.include_router(websocket_router)


@app.on_event("startup")
async def startup_event():
    logger.info("Unhinged Agent Server is alive. Awaiting WebSocket connections...")


@app.get("/health")
async def health_check():
    return {"status": "alive", "system": "unhinged"}
