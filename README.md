# 🏛️ JanSeva AI Assistant

> **A Multilingual, Voice-Enabled GenAI Agent for Indian Government Scheme Discovery**

JanSeva AI helps users cut through the complexity of India's government scheme landscape. Instead of manually searching dozens of scheme pages to figure out what applies to them, users describe themselves once — through text or voice — and get back a filtered, personalized list of schemes they're actually eligible for, along with a direct link to the official government portal to apply.

🔗 **Live Demo:** [janseva-ai-assistant.onrender.com](https://janseva-ai-assistant.onrender.com)

---

## 🎯 What This Solves

Government scheme portals are large, fragmented, and hard to navigate — a user often doesn't know which of the 50+ schemes even apply to them without reading through pages of eligibility criteria one by one.

JanSeva AI doesn't replace the official application process — users still apply on the government's own portal. What it does is:

- Take a user's basic profile (age, income, occupation, location, gender) through a natural conversation, in text or voice
- Instantly filter it against a structured database of **50+ Indian government schemes**
- Return only the schemes the user is actually eligible for (or *possibly* eligible for, if some info is missing)
- Point them directly to the correct official page to apply — no more guessing or getting lost in unrelated scheme listings

This saves time for anyone overwhelmed by government websites, and gives them a clear, upfront understanding of exactly how many schemes they qualify for before they go apply.

---

## 🎙️ Key Design Principles

- **Voice-First Accessibility:** Includes Speech-to-Text (STT) via **Groq Whisper** and Text-to-Speech (TTS) via **gTTS**, so users can interact by speaking instead of typing.
- **Deterministic Eligibility Engine:** To prevent LLM hallucinations on critical government policy decisions, eligibility is decided by a strict, auditable Python rule engine (`eligibility.py`) against structured scheme data (`schemes.json`) — never by the LLM. The LLM is used only for understanding user input (NLU) and generating friendly, natural-language responses (NLG).
- **Multilingual by Design:** Supports English, Hindi (Devanagari script), and Hinglish (Hindi written in Roman script), auto-detected from the user's own message.
- **Ultra-Low Latency:** Uses Groq's LPU infrastructure for both the LLM (Llama 3.3 70B) and Whisper large-v3, enabling near-instant conversational responses.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend Framework** | FastAPI, Uvicorn, Pydantic |
| **Agentic Orchestration** | LangGraph, LangChain |
| **LLM Engine** | Groq API (`llama-3.3-70b-versatile`) |
| **Voice Processing** | Groq Whisper (`whisper-large-v3`) for STT, gTTS for TTS |
| **Logic & Data Engine** | Deterministic Python rule engine + JSON dataset (50+ schemes) |
| **Frontend** | HTML5, CSS, Vanilla JavaScript (MediaRecorder API, Fetch API) |
| **Deployment** | Render |

---

## 🧠 How It Works

1. User sends a message (typed or spoken) through the web UI.
2. If spoken, audio is transcribed to text using **Groq Whisper**.
3. The text is passed into a **LangGraph** agent pipeline with four steps:
   - **Extract Info** — an LLM call parses the conversation to extract a structured profile (age, income, occupation, location, gender) and detects the user's language.
   - **Check Missing Fields** — if critical profile fields are missing, the agent asks a short follow-up question and pauses for the next reply.
   - **Match Schemes** — once enough info is available, a deterministic Python rule engine (no LLM involved) checks the profile against every scheme's eligibility criteria.
   - **Generate Response** — an LLM call turns the matched results into a clear, friendly response in the user's detected language, including how to apply and links to the official portal.
4. If the interaction was voice-based, the reply is converted back to speech using **gTTS**.
5. The response — text, matched schemes, and (if applicable) audio — is returned to the frontend.

---

## 📂 Project Structure

```
govt-scheme-assistant/
├── app.py
├── agent.py
├── eligibility.py
├── voice.py
├── schemes.json
├── Procfile
├── requirements.txt
├── env.example
├── .gitignore
│
└── static/
    ├── index.html
    ├── script.js
    └── style.css
```

---

## 🚀 Deployment

This project is live, deployed on **Render**, using the included `Procfile` to define the start command (`uvicorn app:app --host 0.0.0.0 --port $PORT`).

---

## 🔭 Future Improvements

- Move scheme data and session storage to a proper database for scalability
- Add authentication and rate-limiting
- Expand scheme coverage and add automated sync with official scheme sources
- Guided, fully voice-driven flow for low-literacy users
