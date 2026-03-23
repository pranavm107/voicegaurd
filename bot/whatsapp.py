"""
Twilio WhatsApp webhook handler.
Receives voice notes → runs detection → replies with verdict.
"""
import os
import shutil
import tempfile
import subprocess
import httpx
from loguru import logger
from twilio.twiml.messaging_response import MessagingResponse


def download_media(media_url: str) -> tuple[bytes, str]:
    """Download media from Twilio URL using Basic Auth."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")

    with httpx.Client() as client:
        response = client.get(
            media_url,
            auth=(account_sid, auth_token),
            follow_redirects=True,
            timeout=30.0,
        )
        response.raise_for_status()

    content_type = response.headers.get("content-type", "audio/ogg")
    if "ogg" in content_type:
        ext = ".ogg"
    elif "mpeg" in content_type or "mp3" in content_type:
        ext = ".mp3"
    elif "wav" in content_type:
        ext = ".wav"
    else:
        ext = ".ogg"

    return response.content, ext


def convert_to_wav(input_path: str, output_path: str) -> None:
    """Convert audio to 16kHz mono WAV using ffmpeg."""
    cmd = ["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1", output_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")


def format_whatsapp_reply(result: dict) -> str:
    """Format the analysis result as a clean WhatsApp message."""
    verdict = result["verdict"]
    confidence = result["confidence"]
    risk = result["risk_level"]
    artifacts = result.get("artifacts", [])
    duration = result.get("duration_seconds", 0)

    artifact_lines = "\n".join(f"  - {a}" for a in artifacts)

    if verdict == "FAKE":
        status_line = "WARNING: This voice shows signs of AI generation."
        emoji = "ALERT"
    elif verdict == "REAL":
        status_line = "No deepfake artifacts detected in this sample."
        emoji = "CLEAR"
    else:
        status_line = "Unable to determine with confidence. Recommend human review."
        emoji = "INCONCLUSIVE"

    return (
        f"VoiceGuard AI Analysis [{emoji}]\n\n"
        f"Verdict: {verdict} ({confidence}% confidence)\n"
        f"Risk Level: {risk}\n"
        f"Audio Duration: {round(duration, 1)}s\n\n"
        f"Detected artifacts:\n{artifact_lines}\n\n"
        f"{status_line}\n\n"
        f"--- VoiceGuard AI v0.1 ---"
    )


async def handle_whatsapp_webhook(form_data: dict) -> str:
    """
    Main webhook handler.
    Processes incoming WhatsApp message, runs detection, returns TwiML reply.
    """
    response = MessagingResponse()
    msg = response.message()

    media_url = form_data.get("MediaUrl0")
    num_media = int(form_data.get("NumMedia", 0))

    if num_media == 0 or not media_url:
        msg.body(
            "Send me a voice note or audio file and I will analyze it for deepfake artifacts.\n\n"
            "Supported formats: OGG, MP3, WAV, M4A"
        )
        return str(response)

    tmp_dir = tempfile.mkdtemp()
    try:
        logger.info(f"Downloading media from: {media_url}")
        audio_bytes, ext = download_media(media_url)

        if len(audio_bytes) > 10 * 1024 * 1024:
            msg.body("File too large. Please send audio under 10MB.")
            return str(response)

        raw_path = f"{tmp_dir}/input{ext}"
        with open(raw_path, "wb") as f:
            f.write(audio_bytes)

        wav_path = f"{tmp_dir}/audio.wav"
        if ext != ".wav":
            convert_to_wav(raw_path, wav_path)
        else:
            shutil.copy(raw_path, wav_path)

        from ml.detector import run_detection
        from ml.analyzer import analyze_artifacts

        detection = run_detection(wav_path)
        detection["artifacts"] = analyze_artifacts(wav_path)

        msg.body(format_whatsapp_reply(detection))
        logger.success(f"Analysis complete: {detection['verdict']} {detection['confidence']}%")

    except Exception as e:
        logger.error(f"WhatsApp handler error: {e}")
        msg.body(
            "Sorry, I could not analyze that audio.\n"
            "Please make sure it is a valid voice note or audio file and try again."
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return str(response)
