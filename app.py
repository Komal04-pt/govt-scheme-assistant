import json
import os
import uuid
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import run_agent
from voice import transcribe_audio, synthesize_speech

app = FastAPI(title="JanSeva AI Assistant")

# Add CORS Middleware for production deployments
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store
SESSIONS = {}


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    profile: dict
    eligible_schemes: list
    possibly_eligible_schemes: list


class VoiceChatResponse(BaseModel):
    session_id: str
    transcript: str          # what the user said (from STT)
    reply: str               # text of the assistant's reply
    audio_url: str            # where to play the spoken reply from
    profile: dict
    eligible_schemes: list
    possibly_eligible_schemes: list


def _run_turn(session_id: str, user_message: str):
    """Shared logic: push user message through the agent, update session, return result."""
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
    """Safely extract scheme names from eligible and possibly eligible lists."""
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


# ================= ELIGIBILITY WIZARD DYNAMIC API =================

@app.post("/api/check-eligibility")
async def check_eligibility_api(request: Request):
    """
    Dynamic Filtering Engine reading directly from schemes.json based on criteria.
    """
    try:
        data = await request.json() or {}
        
        user_age = int(data.get('age', 0))
        user_gender = str(data.get('gender', 'any')).lower()
        user_state = str(data.get('state', 'ALL')).upper()
        user_occupation = str(data.get('occupation', 'any')).lower()
        user_income = int(data.get('income', 9999999))

        json_path = os.path.join(os.path.dirname(__file__), "schemes.json")
        if not os.path.exists(json_path):
            return JSONResponse({'success': False, 'error': 'schemes.json file not found'}, status_code=404)

        with open(json_path, 'r', encoding='utf-8') as f:
            all_schemes = json.load(f)

        matched_schemes = []
        for scheme in all_schemes:
            elig = scheme.get('eligibility', {})

            # 1. Age Filter
            min_age = elig.get('age_min', 0)
            max_age = elig.get('age_max', 100)
            if not (min_age <= user_age <= max_age):
                continue

            # 2. Gender Filter
            scheme_gender = elig.get('gender', 'any')
            if isinstance(scheme_gender, str):
                scheme_gender = scheme_gender.lower()
                if scheme_gender not in ['any', 'all'] and user_gender != scheme_gender:
                    continue

            # 3. State/Location Filter
            scheme_loc = elig.get('location', 'CENTRAL')
            if scheme_loc != 'CENTRAL' and user_state != 'ALL' and scheme_loc != user_state:
                continue

            # 4. Occupation Filter
            allowed_occ = elig.get('occupation', ['any'])
            if isinstance(allowed_occ, str):
                allowed_occ = [allowed_occ.lower()]
            elif isinstance(allowed_occ, list):
                allowed_occ = [str(o).lower() for o in allowed_occ]

            if 'any' not in allowed_occ and user_occupation not in allowed_occ:
                continue

            # 5. Income Filter
            max_inc = elig.get('income_max')
            if max_inc is not None and user_income > max_inc:
                continue

            matched_schemes.append(scheme)

        return JSONResponse({'success': True, 'matched_schemes': matched_schemes})

    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)


@app.get("/schemes.json")
def get_schemes_json():
    """Serves schemes.json directly for frontend catalog sync."""
    json_path = os.path.join(os.path.dirname(__file__), "schemes.json")
    return FileResponse(json_path)


# ================= EXISTING AI & CHAT ROUTES =================

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    result = _run_turn(session_id, req.message)

    matched = result.get("matched", {})
    eligible_names, possibly_names = _extract_scheme_names(matched)

    return ChatResponse(
        session_id=session_id,
        reply=result.get("reply", ""),
        profile=result.get("profile", {}),
        eligible_schemes=eligible_names,
        possibly_eligible_schemes=possibly_names,
    )


@app.post("/voice-chat", response_model=VoiceChatResponse)
async def voice_chat(session_id: str = Form(default=""), audio: UploadFile = File(...)):
    session_id = session_id or str(uuid.uuid4())
    audio_bytes = await audio.read()

    stt_result = transcribe_audio(audio_bytes, filename=audio.filename or "input.webm")
    transcript = stt_result.get("text", "")

    if not transcript.strip():
        transcript = "Aapki aawaz saaf nahi aayi, kripya dubara boliye."

    if session_id not in SESSIONS:
        SESSIONS[session_id] = {
            "messages": [],
            "profile": {},
            "language": stt_result.get("language", "english")
        }

    result = _run_turn(session_id, transcript)

    audio_url = synthesize_speech(result.get("reply", ""), language=result.get("language", "english"))

    matched = result.get("matched", {})
    eligible_names, possibly_names = _extract_scheme_names(matched)

    return VoiceChatResponse(
        session_id=session_id,
        transcript=transcript,
        reply=result.get("reply", ""),
        audio_url=audio_url,
        profile=result.get("profile", {}),
        eligible_schemes=eligible_names,
        possibly_eligible_schemes=possibly_names,
    )


@app.get("/")
def root():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")