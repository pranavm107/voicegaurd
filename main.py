# main.py
"""VoiceGuard AI — FastAPI application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

from ml.detector import load_model
from api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load ML model on startup, release on shutdown."""
    logger.info("Starting VoiceGuard AI...")
    load_model()
    logger.success("VoiceGuard AI ready")
    yield
    logger.info("Shutting down VoiceGuard AI")


app = FastAPI(
    title="VoiceGuard AI",
    description="Real-time voice deepfake detection API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten for production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "VoiceGuard AI is running", "docs": "/docs"}
