# VoiceGuard AI

Real-time voice deepfake detection system built with FastAPI and HuggingFace transformers.

## Features

- Deepfake audio detection via ML model (`mo-thecreator/deepfake-audio-detection`)
- REST API with Swagger docs
- PDF report generation
- WhatsApp bot integration (Twilio)
- Streamlit dashboard
- Browser extension for live call monitoring

## Requirements

- Python 3.10+
- ffmpeg installed and on PATH

## Setup & Run

**1. Clone and install dependencies**
```bash
git clone <repo-url>
cd voiceguard
pip install -r requirements.txt
```

**2. Configure environment**
```bash
cp .env.example .env
# Edit .env with your Twilio credentials (optional, only needed for WhatsApp bot)
```

**3. Run the API server**
```bash
uvicorn main:app --reload --port 8000
```

**4. Run the Streamlit dashboard** (separate terminal)
```bash
streamlit run dashboard/app.py
```

## API

Interactive docs: http://localhost:8000/docs

Key endpoint:
```
POST /api/v1/analyze
Content-Type: multipart/form-data
Body: file=<audio file (.wav, .mp3, etc.)>
```

Example with curl:
```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -F "file=@your_audio.wav"
```

## Browser Extension

Load the `extension/` folder as an unpacked extension in Chrome (`chrome://extensions` → Load unpacked).

## WhatsApp Bot

Requires Twilio credentials in `.env`. Configure your Twilio webhook to point to:
```
POST http://<your-host>/api/v1/whatsapp
```
