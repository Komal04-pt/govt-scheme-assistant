"""
Voice layer: Speech-to-Text (STT) and Text-to-Speech (TTS).

STT: Groq's hosted Whisper (whisper-large-v3) — fast, free-tier, good
     Hindi/Indian-language support, returns both transcript and detected
     language.
TTS: gTTS (Google Text-to-Speech) — free, simple, supports Hindi and
     English well. Swap for AI4Bharat Indic-TTS later for more languages
     or a more natural rural-accent voice.

Design note: this layer is intentionally decoupled from agent.py — the
agent still just sees plain text messages. Voice is purely an input/output
adapter on top of the same text pipeline, so the core agent logic doesn't
need to change to support voice.
"""

import os
import io
import uuid
import tempfile

from groq import Groq
from gtts import gTTS

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
groq_client = Groq(api_key=GROQ_API_KEY)

# Our internal language labels -> gTTS language codes
LANG_TO_TTS_CODE = {
    "hindi": "hi",
    "english": "en",
}

AUDIO_OUT_DIR = os.path.join(os.path.dirname(__file__), "static", "audio")
os.makedirs(AUDIO_OUT_DIR, exist_ok=True)


def transcribe_audio(audio_bytes: bytes, filename: str = "input.webm") -> dict:
    """
    Sends audio to Groq Whisper for transcription.
    Returns {"text": str, "language": "hindi"/"english"/other}
    """
    # Groq SDK expects a file-like object with a name attribute for format detection
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename

    transcription = groq_client.audio.transcriptions.create(
        file=audio_file,
        model="whisper-large-v3",
        response_format="verbose_json",  # includes detected "language"
    )

    detected_lang_raw = getattr(transcription, "language", "") or ""
    # Whisper returns full language names like "hindi", "english" already in most cases
    language = "hindi" if "hi" in detected_lang_raw.lower() else "english"

    return {"text": transcription.text.strip(), "language": language}


def synthesize_speech(text: str, language: str = "english") -> str:
    """
    Converts text to speech using gTTS, saves an mp3 file, and returns
    the relative URL path to serve it from /static/audio/.
    """
    lang_code = LANG_TO_TTS_CODE.get(language, "en")

    # gTTS can choke on very long text; keep it reasonably capped for a
    # snappy voice response (full text is still shown/available as text).
    speech_text = text if len(text) < 1500 else text[:1500]

    tts = gTTS(text=speech_text, lang=lang_code, slow=False)

    filename = f"{uuid.uuid4().hex}.mp3"
    filepath = os.path.join(AUDIO_OUT_DIR, filename)
    tts.save(filepath)

    return f"/static/audio/{filename}"
