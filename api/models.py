# api/models.py
"""Pydantic request/response schemas for VoiceGuard API."""
from pydantic import BaseModel
from datetime import datetime
from typing import Literal


class AnalysisResponse(BaseModel):
    verdict: Literal["FAKE", "REAL", "INCONCLUSIVE"]
    confidence: int                  # 0–100
    risk_level: Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"]
    artifacts: list[str]
    duration_seconds: float
    processing_time_ms: int
    file_hash: str
    timestamp: str


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    version: str = "0.1.0"


class ErrorResponse(BaseModel):
    error: str
    detail: str
