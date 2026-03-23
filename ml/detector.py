# ml/detector.py
import time
import hashlib
from pathlib import Path
from contextlib import asynccontextmanager
from loguru import logger

_detector_pipeline = None

def load_model():
    """Load HuggingFace deepfake detection model into memory once."""
    global _detector_pipeline
    from transformers import pipeline
    try:
        logger.info("Loading primary model: mo-thecreator/deepfake-audio-detection")
        _detector_pipeline = pipeline(
            "audio-classification",
            model="mo-thecreator/deepfake-audio-detection"
        )
        logger.success("Primary model loaded successfully")
    except Exception as e:
        logger.warning(f"Primary model failed: {e}. Loading fallback...")
        _detector_pipeline = pipeline(
            "audio-classification",
            model="Rajaram1996/Hubert_DF_Detection"
        )
        logger.success("Fallback model loaded")

def get_pipeline():
    """Return the loaded pipeline. Raises if not loaded."""
    if _detector_pipeline is None:
        raise RuntimeError("Model not loaded. Call load_model() first.")
    return _detector_pipeline

def run_detection(wav_path: str) -> dict:
    """
    Run deepfake detection on a WAV file.
    Returns verdict, raw_score, confidence, file_hash, duration.
    """
    import librosa
    import soundfile as sf

    start = time.time()

    # File hash for chain of custody
    with open(wav_path, "rb") as f:
        file_hash = hashlib.md5(f.read()).hexdigest()

    # Duration check
    audio, sr = librosa.load(wav_path, sr=16000, mono=True)
    duration = len(audio) / sr

    if duration < 1.0:
        raise ValueError(f"Audio too short: {duration:.1f}s (minimum 1s)")
    if duration > 300:
        raise ValueError(f"Audio too long: {duration:.0f}s (maximum 300s)")

    # Run model — save resampled temp file if needed
    pipe = get_pipeline()
    results = pipe(wav_path)

    # results = [{"label": "FAKE", "score": 0.94}, {"label": "REAL", "score": 0.06}]
    top = max(results, key=lambda x: x["score"])
    label = top["label"].upper()
    raw_score = top["score"]

    # Soften confidence — avoid extreme 99.9% claims
    confidence = int(50 + (raw_score - 0.5) * 80)
    confidence = max(10, min(95, confidence))

    # Risk level
    if label == "FAKE" and confidence >= 75:
        risk = "HIGH"
    elif label == "FAKE" and confidence >= 55:
        risk = "MEDIUM"
    elif confidence < 55:
        label = "INCONCLUSIVE"
        risk = "UNKNOWN"
    else:
        risk = "LOW"

    processing_time = int((time.time() - start) * 1000)

    return {
        "verdict": label,
        "confidence": confidence,
        "risk_level": risk,
        "raw_score": raw_score,
        "duration_seconds": round(duration, 2),
        "file_hash": file_hash,
        "processing_time_ms": processing_time,
    }
