# api/routes.py
"""All API route definitions for VoiceGuard."""
import os
import shutil
import tempfile
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import Response
from loguru import logger

from ml.detector import run_detection, get_pipeline
from ml.analyzer import analyze_artifacts
from api.models import AnalysisResponse, HealthResponse

router = APIRouter()

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".ogg", ".m4a", ".flac"}


def convert_to_wav(input_path: str, output_path: str) -> None:
    """Convert any audio format to 16kHz mono WAV using ffmpeg."""
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-ar", "16000", "-ac", "1", "-f", "wav",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg conversion failed: {result.stderr}")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check — confirms API and model status."""
    try:
        get_pipeline()
        model_loaded = True
    except RuntimeError:
        model_loaded = False
    return HealthResponse(status="ok", model_loaded=model_loaded)


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_audio(file: UploadFile = File(...)):
    """
    Analyze an audio file for deepfake artifacts.
    Accepts WAV, MP3, OGG, M4A, FLAC. Max size 10MB.
    """
    # Validate extension
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported format: {suffix}. Use: {ALLOWED_EXTENSIONS}")

    # Validate file size (10MB)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "File too large. Maximum size is 10MB.")

    tmp_dir = tempfile.mkdtemp()
    try:
        # Save upload
        raw_path = os.path.join(tmp_dir, f"input{suffix}")
        with open(raw_path, "wb") as f:
            f.write(content)

        # Convert to WAV if needed
        wav_path = os.path.join(tmp_dir, "audio.wav")
        if suffix != ".wav":
            convert_to_wav(raw_path, wav_path)
        else:
            shutil.copy(raw_path, wav_path)

        # Run detection + artifact analysis
        detection = run_detection(wav_path)
        artifacts = analyze_artifacts(wav_path)

        return AnalysisResponse(
            verdict=detection["verdict"],
            confidence=detection["confidence"],
            risk_level=detection["risk_level"],
            artifacts=artifacts,
            duration_seconds=detection["duration_seconds"],
            processing_time_ms=detection["processing_time_ms"],
            file_hash=detection["file_hash"],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(500, f"Analysis failed: {str(e)}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.post("/whatsapp", include_in_schema=False)
async def whatsapp_webhook(request: Request):
    """Twilio WhatsApp webhook endpoint."""
    from bot.whatsapp import handle_whatsapp_webhook
    form_data = await request.form()
    form_dict = dict(form_data)
    twiml = await handle_whatsapp_webhook(form_dict)
    return Response(content=twiml, media_type="application/xml")
