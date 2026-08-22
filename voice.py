import os
import io
import re
import time
import uuid
from groq import Groq
from gtts import gTTS

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
groq_client = Groq(api_key=GROQ_API_KEY)

LANG_TO_TTS_CODE = {
    "hindi": "hi",
    "hindi_devanagari": "hi",
    "hinglish": "hi",
    "english": "en",
}

AUDIO_OUT_DIR = os.path.join(os.path.dirname(__file__), "static", "audio")
os.makedirs(AUDIO_OUT_DIR, exist_ok=True)

AUDIO_MAX_AGE_SECONDS = 60 * 60  # 1 hour


def _cleanup_old_audio_files():
    """
    Deletes audio files older than AUDIO_MAX_AGE_SECONDS from the audio
    output directory. Called on every synthesize_speech() invocation so
    the folder never grows unbounded, without needing a separate
    scheduled job or background process.
    """
    try:
        now = time.time()
        for fname in os.listdir(AUDIO_OUT_DIR):
            fpath = os.path.join(AUDIO_OUT_DIR, fname)
            if not os.path.isfile(fpath):
                continue
            file_age = now - os.path.getmtime(fpath)
            if file_age > AUDIO_MAX_AGE_SECONDS:
                try:
                    os.remove(fpath)
                except Exception as cleanup_err:
                    print(f"Failed to remove old audio file {fname}: {cleanup_err}")
    except Exception as e:
        print("Audio cleanup exception:", str(e))


def _clean_text_for_tts(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'http\S+|www\.\S+', '', text)
    text = re.sub(r'[*#_\\`~]', '', text)
    text = re.sub(r'^\s*[-+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def transcribe_audio(audio_bytes: bytes, filename: str = "input.webm") -> dict:
    try:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = filename

        transcription = groq_client.audio.transcriptions.create(
            file=audio_file,
            model="whisper-large-v3",
            response_format="verbose_json",
        )

        raw_text = transcription.text.strip() if hasattr(transcription, "text") else ""
        detected_lang_raw = getattr(transcription, "language", "") or ""

        if "hi" in detected_lang_raw.lower() or any('\u0900' <= char <= '\u097F' for char in raw_text):
            language = "hindi_devanagari"
        elif any(w in raw_text.lower() for w in ["hai", "hoon", "kaise", "aap", "chahiye"]):
            language = "hinglish"
        else:
            language = "english"

        return {"text": raw_text, "language": language}

    except Exception as e:
        print("Transcription Exception:", str(e))
        return {"text": "", "language": "english"}


def synthesize_speech(text: str, language: str = "english") -> str:
    try:
        _cleanup_old_audio_files()

        clean_text = _clean_text_for_tts(text)
        if not clean_text:
            return ""

        lang_code = LANG_TO_TTS_CODE.get(language, "hi" if any('\u0900' <= c <= '\u097F' for c in clean_text) else "en")
        speech_text = clean_text[:1200]

        if lang_code == "en":
            tts = gTTS(text=speech_text, lang="en", tld="co.in", slow=False)
        else:
            tts = gTTS(text=speech_text, lang="hi", slow=False)

        filename = f"{uuid.uuid4().hex}.mp3"
        filepath = os.path.join(AUDIO_OUT_DIR, filename)
        tts.save(filepath)

        return f"/static/audio/{filename}"

    except Exception as e:
        print("Synthesize Speech Exception:", str(e))
        return ""