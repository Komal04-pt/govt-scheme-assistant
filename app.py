import json
import os
import uuid
import logging
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import run_agent
from voice import transcribe_audio, synthesize_speech
from eligibility import match_all_schemes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="JanSeva AI Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path.endswith(".json"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

SESSIONS = {}

STATE_MAP = {
    'BR': 'br',
    'RJ': 'rj',
    'UP': 'up',
    'MP': 'mp',
    'DL': 'dl',
    'MH': 'mh',
    'KA': 'ka',
    'WB': 'wb'
}

class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str

class ChatResponse(BaseModel):
    session_id: str
    reply: str
    audio_url: str = ""
    profile: dict
    eligible_schemes: list
    possibly_eligible_schemes: list

class VoiceChatResponse(BaseModel):
    session_id: str
    transcript: str
    reply: str
    audio_url: str
    profile: dict
    eligible_schemes: list
    possibly_eligible_schemes: list

class EligibilityCheckRequest(BaseModel):
    age: str | int | None = None
    gender: str | None = None
    state: str = "ALL"
    occupation: str | None = None
    income: str | int | None = None


def _run_turn(session_id: str, user_message: str):
    session = SESSIONS.get(session_id, {"messages": [], "profile": {}, "language": "english"})
    session["messages"].append({"role": "user", "content": user_message})

    result = run_agent(
        messages=session["messages"],
        profile=session["profile"],
        language=session.get("language", "english"),
    )

    session["profile"] = result.get("profile", {})
    session["language"] = result.get("language", "english")
    session["messages"].append({"role": "assistant", "content": result.get("reply", "")})
    SESSIONS[session_id] = session
    return result

def _extract_scheme_names(matched_data):
    eligible_raw = matched_data.get("eligible", [])
    possibly_raw = matched_data.get("possibly_eligible", [])

    eligible_names = []
    for s in eligible_raw:
        if isinstance(s, dict):
            eligible_names.append(s.get("name", s.get("title", "Unknown Scheme")))

    possibly_names = []
    for p in possibly_raw:
        if isinstance(p, tuple) and len(p) > 0 and isinstance(p[0], dict):
            possibly_names.append(p[0].get("name", p[0].get("title", "Unknown Scheme")))
        elif isinstance(p, dict):
            possibly_names.append(p.get("name", p.get("title", "Unknown Scheme")))

    return eligible_names, possibly_names

@app.get("/api/schemes")
async def get_filtered_schemes(state: str = "ALL"):
    json_path = os.path.join(os.path.dirname(__file__), "schemes.json")
    if not os.path.exists(json_path):
        return JSONResponse([], status_code=200)

    with open(json_path, 'r', encoding='utf-8') as f:
        all_schemes = json.load(f)

    if state.upper() == "ALL":
        return JSONResponse(all_schemes)

    target_code = state.upper()
    target_lower = STATE_MAP.get(target_code, state.lower())
    filtered = []

    for s in all_schemes:
        elig = s.get('eligibility', {})
        loc = str(elig.get('location', s.get('state', 'CENTRAL'))).lower()

        if loc in ['central', 'all', 'all india'] or loc == target_code.lower() or loc == target_lower:
            filtered.append(s)

    return JSONResponse(filtered)


@app.post("/api/check-eligibility")
async def check_eligibility_api(request: Request):
    """
    NOTE: This route previously re-implemented its own eligibility filtering
    loop, separate from eligibility.py's rule engine. That meant this API
    and the conversational /chat agent could silently disagree on the same
    user's eligibility if the rules ever diverged. It now reuses
    match_all_schemes() from eligibility.py, so there's a single source of
    truth for eligibility logic across the whole app.

    It also previously crashed with int(data.get('age', 0)) if age/income
    arrived as a non-numeric string (e.g. "22 years", "3 lakh") — the same
    class of bug found earlier in eligibility.py. match_all_schemes()
    already normalizes numeric fields safely via _to_number(), so that
    risk is gone here too.
    """
    try:
        data = await request.json() or {}

        user_state_raw = str(data.get('state', 'ALL')).upper()
        # "ALL" means the user didn't specify a state. Previously this
        # skipped location filtering entirely, which meant a state-specific
        # scheme (e.g. an MP-only scheme) could incorrectly show up for a
        # user in a completely different state. Passing location=None here
        # lets the tri-state rule engine correctly mark such schemes as
        # "possibly_eligible" (unknown) instead of wrongly "eligible" —
        # consistent with this project's core design goal of never
        # asserting eligibility the code can't actually confirm.
        user_location = None if user_state_raw == "ALL" else STATE_MAP.get(user_state_raw, user_state_raw.lower())

        profile = {
            "age": data.get("age"),
            "gender": data.get("gender"),
            "location": user_location,
            "occupation": data.get("occupation"),
            "annual_income": data.get("income"),
        }

        result = match_all_schemes(profile)

        return JSONResponse({
            'success': True,
            'matched_schemes': result.get("eligible", []),
        })

    except Exception as e:
        logger.error(f"Eligibility error: {e}")
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)


@app.get("/schemes.json")
def get_schemes_json():
    json_path = os.path.join(os.path.dirname(__file__), "schemes.json")
    return FileResponse(json_path)

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        session_id = req.session_id or str(uuid.uuid4())
        result = _run_turn(session_id, req.message)

        audio_url = ""
        try:
            audio_url = synthesize_speech(result.get("reply", ""), language=result.get("language", "english")) or ""
        except Exception as tts_err:
            logger.error(f"TTS Error in /chat: {tts_err}")
            audio_url = ""

        matched = result.get("matched", {})
        eligible_names, possibly_names = _extract_scheme_names(matched)

        return ChatResponse(
            session_id=session_id,
            reply=result.get("reply", ""),
            audio_url=audio_url,
            profile=result.get("profile", {}),
            eligible_schemes=eligible_names,
            possibly_eligible_schemes=possibly_names,
        )
    except Exception as e:
        logger.error(f"Chat execution error: {e}")
        return JSONResponse({'error': f"Chat processing failed: {str(e)}"}, status_code=500)

@app.post("/voice-chat", response_model=VoiceChatResponse)
async def voice_chat(session_id: str = Form(default=""), audio: UploadFile = File(...)):
    try:
        session_id = session_id or str(uuid.uuid4())
        audio_bytes = await audio.read()

        if not audio_bytes:
            return JSONResponse({'error': 'Empty audio payload'}, status_code=400)

        try:
            stt_result = transcribe_audio(audio_bytes, filename=audio.filename or "input.webm")
            if isinstance(stt_result, dict):
                transcript = stt_result.get("text", "")
                language = stt_result.get("language", "english")
            else:
                transcript = str(stt_result)
                language = "english"
        except Exception as stt_err:
            logger.error(f"STT Error: {stt_err}")
            transcript = ""
            language = "english"

        if not transcript or not transcript.strip():
            transcript = "Aapki aawaz saaf nahi aayi, kripya dubara boliye."

        if session_id not in SESSIONS:
            SESSIONS[session_id] = {
                "messages": [],
                "profile": {},
                "language": language
            }

        result = _run_turn(session_id, transcript)

        audio_url = ""
        try:
            audio_url = synthesize_speech(result.get("reply", ""), language=result.get("language", "english")) or ""
        except Exception as tts_err:
            logger.error(f"TTS Error: {tts_err}")
            audio_url = ""

        matched = result.get("matched", {})
        eligible_names, possibly_names = _extract_scheme_names(matched)

        return VoiceChatResponse(
            session_id=session_id,
            transcript=transcript,
            reply=result.get("reply", "Mein aapki kaise madad kar sakta hoon?"),
            audio_url=audio_url,
            profile=result.get("profile", {}),
            eligible_schemes=eligible_names,
            possibly_eligible_schemes=possibly_names,
        )
    except Exception as e:
        logger.error(f"Fatal Voice Endpoint Error: {e}")
        return JSONResponse({'error': f"Voice error: {str(e)}"}, status_code=500)

@app.get("/")
def root():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")