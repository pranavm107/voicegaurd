# bot/whatsapp.py
import os
import shutil
import tempfile
import subprocess
import httpx
from loguru import logger
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse


def get_twilio_client():
    return Client(
        os.getenv("TWILIO_ACCOUNT_SID"),
        os.getenv("TWILIO_AUTH_TOKEN")
    )


def download_media(media_url: str) -> tuple[bytes, str]:
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")

    with httpx.Client() as client:
        response = client.get(
            media_url,
            auth=(account_sid, auth_token),
            follow_redirects=True,
            timeout=30.0
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
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-ar", "16000", "-ac", "1", output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")


def format_reply(result: dict) -> str:
    verdict = result["verdict"]
    confidence = result["confidence"]
    risk = result["risk_level"]
    artifacts = result.get("artifacts", [])
    duration = result.get("duration_seconds", 0)

    artifact_lines = "\n".join(f"  - {a}" for a in artifacts)

    if verdict == "FAKE":
        status_line = "WARNING: This voice shows signs of AI generation. Do not trust without verification."
        tag = "[ALERT]"
    elif verdict == "REAL":
        status_line = "No deepfake artifacts detected in this sample."
        tag = "[CLEAR]"
    else:
        status_line = "Unable to determine. Recommend human review."
        tag = "[INCONCLUSIVE]"

    return (
        f"VoiceGuard AI Analysis {tag}\n\n"
        f"Verdict: {verdict} ({confidence}% confidence)\n"
        f"Risk Level: {risk}\n"
        f"Duration: {round(duration, 1)}s\n\n"
        f"Detected artifacts:\n{artifact_lines}\n\n"
        f"{status_line}\n\n"
        f"--- VoiceGuard AI v0.1 ---"
    )


def send_whatsapp_message(to_number: str, body: str) -> None:
    """Send message using Twilio REST API directly — more reliable than TwiML for international."""
    client = get_twilio_client()
    from_number = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

    message = client.messages.create(
        from_=from_number,
        to=to_number,
        body=body
    )
    logger.info(f"Message sent SID: {message.sid}, Status: {message.status}")


async def handle_whatsapp_webhook(form_data: dict) -> str:
    """Main webhook handler — processes voice note and sends reply via REST API."""

    # Always return empty TwiML immediately (200 OK to Twilio)
    empty_response = str(MessagingResponse())

    from_number = form_data.get("From", "")
    media_url = form_data.get("MediaUrl0")
    num_media = int(form_data.get("NumMedia", 0))

    logger.info(f"Incoming from: {from_number}, media count: {num_media}")

    # No audio attached
    if num_media == 0 or not media_url:
        send_whatsapp_message(
            from_number,
            "Send me a voice note or audio file and I will analyze it for deepfakes.\n\nSupported: OGG, MP3, WAV, M4A"
        )
        return empty_response

    tmp_dir = tempfile.mkdtemp()
    try:
        # Send "processing" message immediately so user knows it's working
        send_whatsapp_message(
            from_number,
            "VoiceGuard AI is analyzing your audio... Please wait 30-60 seconds."
        )

        # Download audio
        logger.info(f"Downloading media from: {media_url}")
        audio_bytes, ext = download_media(media_url)

        if len(audio_bytes) > 10 * 1024 * 1024:
            send_whatsapp_message(from_number, "File too large. Please send audio under 10MB.")
            return empty_response

        # Save and convert
        raw_path = f"{tmp_dir}/input{ext}"
        with open(raw_path, "wb") as f:
            f.write(audio_bytes)

        wav_path = f"{tmp_dir}/audio.wav"
        if ext != ".wav":
            convert_to_wav(raw_path, wav_path)
        else:
            shutil.copy(raw_path, wav_path)

        # Run detection
        from ml.detector import run_detection
        from ml.analyzer import analyze_artifacts

        detection = run_detection(wav_path)
        artifacts = analyze_artifacts(wav_path)
        detection["artifacts"] = artifacts

        reply = format_reply(detection)

        # Send result via REST API
        send_whatsapp_message(from_number, reply)
        logger.success(f"Reply sent to {from_number}: {detection['verdict']} {detection['confidence']}%")

    except Exception as e:
        logger.error(f"WhatsApp handler error: {e}")
        send_whatsapp_message(
            from_number,
            "Sorry, analysis failed. Please send a valid voice note and try again."
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return empty_response