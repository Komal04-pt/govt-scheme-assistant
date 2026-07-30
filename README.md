# 🏛️ JanSeva AI Assistant

> **A Multilingual, Voice-Enabled GenAI Agent for Indian Government Scheme Discovery**

JanSeva AI bridges the information gap between citizens (especially rural and low-literacy communities) and public welfare programs. Built on **FastAPI**, **LangGraph**, and **Llama 3.3 70B via Groq**, it enables seamless, natural voice and text interactions in Hindi and English.

---

## 🎯 Key Design Principles

* 🎙️ **Voice-First Accessibility:** Includes direct Speech-to-Text (STT) via **Groq Whisper** and Text-to-Speech (TTS) via **gTTS**. Designed so low-literacy users can discover benefits purely through voice without reading or typing.
* ⚙️ **Deterministic Eligibility Engine:** To prevent LLM hallucinations on critical government policies, eligibility decisions are handled by a strict, auditable Python engine (`eligibility.py`) against structured scheme rules (`schemes.json`). The LLM is strictly used for Natural Language Understanding (NLU) and friendly response generation.
* ⚡ **Ultra-Low Latency:** Leveraging Groq's LPU infrastructure for both Llama 3.3 70B and Whisper large-v3 for near-instant conversational responses.

---

## 🛠️ Tech Stack

* **Backend Framework:** FastAPI, Uvicorn, Pydantic
* **Agentic Orchestration:** LangGraph, LangChain
* **LLM Engine:** Groq API (`llama-3.3-70b-versatile`)
* **Voice Processing:** Groq Whisper (`whisper-large-v3`), gTTS
* **Logic & Data Engine:** Deterministic Python Rule Engine, JSON Database
* **Frontend:** HTML5, Modern CSS, Vanilla JavaScript (MediaRecorder API, Fetch API)

---

## 📂 Project Structure

```text
govt-scheme-assistant/
├── app.py              # FastAPI Web Server (/chat & /voice-chat endpoints)
├── agent.py            # LangGraph StateGraph (Extract -> Route -> Match -> Respond)
├── eligibility.py      # Deterministic Rule Engine for Scheme Matching
├── voice.py            # Audio Pipeline (STT via Whisper + TTS via gTTS)
├── schemes.json        # Structured Dataset of 15+ Govt Schemes
├── Procfile            # Deployment Process Configuration
├── requirements.txt    # Project Dependencies
├── .gitignore          # Environment & Cache Exclusions
│
└── static/             # Frontend Assets
    ├── index.html      # Accessible Chat UI with Voice Controls
    ├── script.js       # Real-time Voice Recording & Fetch Logic
    └── style.css       # Responsive UI Styling