# 🏛️ JanSeva AI Assistant

> **A chatbot that helps people find Indian government welfare schemes they qualify for — by voice or text, in English or Hindi.**

Finding the right government scheme in India is hard. There are 50+ schemes spread across different websites, each with its own list of rules about who can apply. Most people don't have time to read through all of them just to find out if they qualify.

JanSeva AI fixes this. A user just talks about themselves — their age, income, job, and location — either by typing or speaking. The app then checks this against every scheme in its database and tells the user exactly which ones they qualify for, along with a link to apply on the official government website.

🔗 **Live Demo:** [janseva-ai-assistant.onrender.com](https://janseva-ai-assistant.onrender.com)

---

## 🎯 What Problem Does It Solve

Government scheme websites are confusing and scattered. A user usually has no way of knowing which schemes apply to them without manually reading through pages of rules, one scheme at a time.

JanSeva AI doesn't replace the actual application process — users still need to apply on the government's official site. What this app does is:

- Take basic details from the user (age, income, job, location, gender) through a normal conversation, typed or spoken
- Compare this instantly against a database of **50+ government schemes**
- Show only the schemes the user actually qualifies for (or *might* qualify for, if some info is still missing)
- Give a direct link to the right page to apply

This saves people time and gives them a clear answer upfront, instead of leaving them to guess.

---

## 🎙️ How It's Built (Key Ideas)

- **You can talk to it:** Speech-to-Text (via **Groq Whisper**) turns your voice into text, and Text-to-Speech (via **gTTS**) reads replies back to you.
- **The AI doesn't decide eligibility on its own:** To prevent LLM hallucinations on critical policy decisions, eligibility is decided by a separate, plain Python rule engine (eligibility.py) against structured scheme data — never by the LLM. The LLM is used only for understanding user input (NLU) and generating friendly, natural-language responses (NLG)
- **One single place for all data:** All scheme details are stored in MongoDB. Both the chatbot and the website's scheme list read from this same place, so they never show different or outdated information.
- **Works in 3 languages:** English, Hindi, and Hinglish — the app figures out which one you're using automatically.
- **Fast responses:** Uses Groq's infrastructure to run the AI models quickly, so replies come back almost instantly.

---

## 🛠️ Tech Stack

| Part of the App | What's Used |
|---|---|
| **Backend** | FastAPI, Uvicorn, Pydantic |
| **Database** | MongoDB (accessed via PyMongo) — stores all scheme data |
| **Connecting to the AI** | LangChain's `ChatGroq` — a simple way to call the Groq API |
| **AI Model** | Groq API |
| **Voice** | Groq Whisper (speech-to-text), gTTS (text-to-speech) |
| **Eligibility Logic** | A custom Python rule-checker, no AI involved |
| **Frontend** | HTML, CSS, plain JavaScript (no framework — uses the browser's built-in MediaRecorder and Fetch APIs) |
| **Hosting** | Render |

---

## 🧠 How It Works, Step by Step

1. User sends a message — typed or spoken — through the website.
2. If it's a voice message, **Groq Whisper** converts it to text first.
3. The text goes through a simple step-by-step process in `agent.py`:
   - **Understand the message** — the AI reads the conversation and pulls out details like age, income, job, and location. It also figures out what language the user is writing in, and what kind of message it is (a new question, a follow-up, a greeting, etc.).
   - **Decide what to do next** — if too much info is still missing, the app asks a quick follow-up question. If the user is just saying "thanks" or "hi", it replies casually. Otherwise, it moves on to checking schemes.
   - **Check eligibility** — a plain Python function (no AI) compares the user's details against every scheme's rules, using live data from MongoDB.
   - **Write the reply** — the AI turns the matched schemes into a clear, friendly answer in the user's language, including how to apply.
4. If the user spoke instead of typing, the reply is also converted to speech using **gTTS**.
5. The final answer (text, matching schemes, and audio if needed) is sent back and shown on the screen.

---

## 📂 Project Files

```
govt-scheme-assistant/
├── app.py
├── agent.py
├── eligibility.py
├── voice.py
├── migrate_json_to_mongo.py
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

**About `schemes.json`:** this file is just used for editing. If a new scheme needs to be added or an existing one changed, it's edited here first, then pushed into MongoDB by running `migrate_json_to_mongo.py`. The live app always reads from MongoDB, never directly from this file.

---

## 🚀 Deployment

This app is live on **Render**. The `Procfile` tells Render how to start it (`uvicorn app:app --host 0.0.0.0 --port $PORT`).

---

## 🔭 What Could Be Added Next

- Login/signup and rate-limiting
- More schemes, and a way to auto-update from official government sources
- A fully voice-guided mode for users who may not be comfortable reading