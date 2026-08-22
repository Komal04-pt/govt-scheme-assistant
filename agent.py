import os
import json
import re
import logging
from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from eligibility import match_all_schemes, search_scheme_by_name, check_eligibility

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

LLM_MODEL = "openai/gpt-oss-120b"

llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model=LLM_MODEL,
    temperature=0.2,
)

CORE_FIELDS = ["occupation", "annual_income", "age", "location", "gender"]


class AgentState(TypedDict):
    messages: List[dict]
    profile: dict
    language: str
    message_type: str
    named_scheme_query: str
    matched: dict
    reply: str
    need_followup: bool


EXTRACTION_SYSTEM_PROMPT = """You are an information extraction assistant for a government welfare scheme eligibility checker in India.

Extract structured profile information, detect user language preference, classify the latest message type, and detect if the user named a specific scheme.

DYNAMIC LANGUAGE DETECTION RULES:
Analyze the LATEST user message carefully:
1. "english": User writes in standard English (e.g., "Tell me about schemes", "I am a student") OR explicitly requests English ("in English").
2. "hindi_devanagari": User writes using actual Devanagari script (e.g. "मुझे योजना बताओ", "हिंदी में लिखो") OR explicitly requests Hindi/Devanagari ("Hindi me likho", "in Hindi").
3. "hinglish": User writes Hindi using Roman/English letters (e.g. "mujhe schemes batayein", "main student hu") OR explicitly requests Hinglish ("Hinglish me batao").

MESSAGE TYPE CLASSIFICATION (classify the LATEST user message only):
1. "new_query": User is asking about schemes, eligibility, or sharing new profile info (e.g. "mujhe schemes batao", "my income is 3 lakh", "education schemes chahiye").
2. "acknowledgment": User is closing the topic, thanking, or confirming understanding without asking anything new (e.g. "ok thank you", "samajh gaya", "theek hai", "got it", "thanks bhai").
3. "greeting": User is only greeting (e.g. "hi", "hello", "namaste") with no other content.
4. "followup_question": User is asking a clarifying/related question about something already discussed (e.g. "iske documents kya chahiye", "isme apply kaise karna hai").

NAMED SCHEME DETECTION:
If the LATEST user message explicitly names a specific government scheme by its title (e.g. "tell me about Lakhpati Didi Scheme", "PM Kisan ke baare mein batao", "eligibility for Sukanya Samriddhi Yojana"), extract that scheme name into "named_scheme_query". If no specific scheme is named, set it to null.

Respond with ONLY a JSON object:
{
  "profile": { "occupation": null, "annual_income": null, "age": null, "gender": null,
               "location": null, "land_owner": null, "house_owner": null,
               "marital_status": null, "user_intent": [], "flags": [] },
  "language": "english",
  "message_type": "new_query",
  "named_scheme_query": null
}
"""


def extract_info(state: AgentState) -> AgentState:
    convo_text = "\n".join(f"{m['role']}: {m['content']}" for m in state["messages"])
    try:
        resp = llm.invoke([
            SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
            HumanMessage(content=f"Conversation history:\n{convo_text}\n\nExtract profile, language preference, message type, and named scheme now."),
        ])
    except Exception as e:
        logger.warning(f"extract_info: LLM call failed: {e}")
        state["profile"] = dict(state.get("profile", {}))
        state["language"] = state.get("language", "hinglish")
        state["message_type"] = "new_query"
        state["named_scheme_query"] = ""
        return state

    try:
        raw = resp.content.strip()
        start_idx = raw.find('{')
        end_idx = raw.rfind('}')
        if start_idx != -1 and end_idx != -1:
            raw = raw[start_idx:end_idx + 1]

        parsed = json.loads(raw)
        new_profile = parsed.get("profile", {})
        language = parsed.get("language", "hinglish")
        message_type = parsed.get("message_type", "new_query")
        named_scheme_query = parsed.get("named_scheme_query") or ""
    except Exception as e:
        logger.warning(f"extract_info: failed to parse LLM JSON output: {e} | raw={resp.content[:200]!r}")
        new_profile = {}
        language = state.get("language", "hinglish")
        message_type = "new_query"
        named_scheme_query = ""

    if state["messages"]:
        last_msg = state["messages"][-1]["content"].lower()
        if "hinglish" in last_msg:
            language = "hinglish"
        elif any(k in last_msg for k in ["हिंदी", "hindi", "देवनागरी"]):
            language = "hindi_devanagari"
        elif any(k in last_msg for k in ["in english", "english please", "speak in english"]):
            language = "english"

        stripped = last_msg.strip().rstrip("!.")
        ack_phrases = [
            "ok thank you", "ok thanks", "thank you", "thanks", "thankyou",
            "samajh gaya", "samajh gyi", "smjh gya", "smjh gyi",
            "theek hai", "thik hai", "got it", "okay got it", "ok got it",
            "achha theek hai", "ok samajh gaya", "shukriya",
        ]
        if any(stripped == phrase or stripped.endswith(phrase) for phrase in ack_phrases):
            message_type = "acknowledgment"

    profile = dict(state.get("profile", {}))
    for k, v in new_profile.items():
        if v not in (None, [], ""):
            if k in ["user_intent", "flags"] and isinstance(v, list):
                existing = profile.get(k, [])
                if isinstance(existing, list):
                    profile[k] = list(set(existing + v))
                else:
                    profile[k] = v
            else:
                profile[k] = v

    state["profile"] = profile
    state["language"] = language
    state["message_type"] = message_type
    state["named_scheme_query"] = named_scheme_query
    return state


def route_after_extraction(state: AgentState) -> str:
    message_type = state.get("message_type", "new_query")

    if state.get("named_scheme_query"):
        return "match_schemes"

    if message_type in ("acknowledgment", "greeting"):
        return "chit_chat"

    profile = state["profile"]
    missing = [f for f in CORE_FIELDS if profile.get(f) in (None, "")]

    if len(missing) >= 4:
        state["need_followup"] = True
        return "ask_followup"
    state["need_followup"] = False
    return "match_schemes"


def ask_followup(state: AgentState) -> AgentState:
    profile = state["profile"]
    missing = [f for f in CORE_FIELDS if profile.get(f) in (None, "")]
    lang = state.get("language", "hinglish")

    if lang == "hindi_devanagari":
        lang_fmt = "Hindi using Devanagari script (हिंदी देवनागरी)"
    elif lang == "english":
        lang_fmt = "Plain English"
    else:
        lang_fmt = "Hinglish (Hindi in Roman script)"

    prompt = f"""The user is seeking Indian government welfare schemes.
Current profile: {json.dumps(profile)}.
Missing info: {missing}.
Write ONE short, friendly follow-up question strictly in {lang_fmt}.
Return ONLY the question text."""

    try:
        resp = llm.invoke([HumanMessage(content=prompt)])
        state["reply"] = resp.content.strip()
    except Exception as e:
        logger.warning(f"ask_followup: LLM call failed: {e}")
        state["reply"] = "Sorry, I'm having trouble right now. Could you please share a bit more about yourself (your occupation, age, income, and location)?"
    return state


def chit_chat_response(state: AgentState) -> AgentState:
    lang = state.get("language", "hinglish")
    message_type = state.get("message_type", "acknowledgment")

    if lang == "hindi_devanagari":
        lang_fmt = "Hindi using Devanagari script (हिंदी देवनागरी)"
    elif lang == "english":
        lang_fmt = "Plain English"
    else:
        lang_fmt = "Hinglish (Hindi in Roman script)"

    prompt = f"""The user just sent a short {message_type} message (like "thank you" or "ok got it"), not a new question.
Write ONE short, warm, natural reply (max 1-2 sentences) strictly in {lang_fmt}.
Do NOT repeat any scheme details or list schemes again.
If it's an acknowledgment, just warmly close the topic and let them know they can ask more anytime.
If it's a greeting, greet back briefly and ask how you can help with government schemes.
Return ONLY the reply text."""

    try:
        resp = llm.invoke([HumanMessage(content=prompt)])
        state["reply"] = resp.content.strip()
    except Exception as e:
        logger.warning(f"chit_chat_response: LLM call failed: {e}")
        state["reply"] = "You're welcome! Feel free to ask anytime. 😊"
    return state


def match_schemes_node(state: AgentState) -> AgentState:
    state["matched"] = match_all_schemes(state["profile"])
    return state


RESPONSE_SYSTEM_PROMPT = """You are 'JanSeva AI Assistant'.

DYNAMIC LANGUAGE & SCRIPT INSTRUCTION:
- You MUST write your complete response strictly in {lang_instruction}.
- DO NOT MIX SCRIPTS. If requested language is 'hindi_devanagari', write 100% in Devanagari Hindi script (हिंदी). If 'english', write 100% in English. If 'hinglish', write in Roman Hindi.

STRICT SCHEME FILTERING & RELEVANCE RULES:
1. **USER INTENT & OCCUPATION STRICT MATCHING**:
   - Filter and prioritize matched schemes strictly based on user query and occupation.
   - If user asks for education/coaching, ONLY return relevant education schemes. Strictly exclude unrelated schemes (solar, pensions, maternity, etc.).
2. **NAMED SCHEME RULE**:
   - If `REQUESTED_SCHEME_INFO` is provided below, the user explicitly asked about that specific scheme. ALWAYS answer directly about it first, using its data. Clearly state whether the user's current known profile appears eligible, possibly eligible, or not eligible for it, based on `REQUESTED_SCHEME_ELIGIBILITY_STATUS` — do not say you don't have information about it if `REQUESTED_SCHEME_INFO` is present.
3. **FALLBACK RULE**:
   - If `MATCHED ELIGIBLE SCHEMES DATA` is empty and there is no `REQUESTED_SCHEME_INFO`, suggest domain-specific schemes relevant to user profile.
4. **FORMATTING**: Use clear markdown bullet points.
"""


def generate_response(state: AgentState) -> AgentState:
    lang = state.get("language", "hinglish")

    if lang == "hindi_devanagari":
        lang_instruction = "Hindi in Devanagari script (हिंदी देवनागरी लिपि). Example: 'आपकी प्रोफाइल के अनुसार...'"
    elif lang == "english":
        lang_instruction = "English language. Example: 'Based on your profile...'"
    else:
        lang_instruction = "Hinglish (Hindi using English/Roman alphabet). Example: 'Aapke profile ke according...'"

    eligible = state["matched"].get("eligible", [])
    possibly = state["matched"].get("possibly_eligible", [])

    eligible_summary = []
    for s in eligible:
        if isinstance(s, dict):
            eligible_summary.append({
                "name": s.get("name_hi") if lang == "hindi_devanagari" and s.get("name_hi") else s.get("name", s.get("title", "")),
                "category": s.get("category", ""),
                "description": s.get("description", ""),
                "benefits": s.get("benefits", ""),
                "how_to_apply": s.get("how_to_apply", ""),
                "documents_required": s.get("documents_required", []),
            })

    possibly_summary = []
    for p in possibly:
        if isinstance(p, tuple) and len(p) == 2 and isinstance(p[0], dict):
            scheme_obj, mf = p[0], p[1]
            possibly_summary.append({
                "name": scheme_obj.get("name_hi") if lang == "hindi_devanagari" and scheme_obj.get("name_hi") else scheme_obj.get("name", scheme_obj.get("title", "")),
                "category": scheme_obj.get("category", ""),
                "missing_fields": mf
            })

    requested_scheme_block = ""
    named_query = state.get("named_scheme_query", "")
    if named_query:
        requested_scheme = search_scheme_by_name(named_query)
        if requested_scheme:
            elig_result = check_eligibility(requested_scheme, state["profile"])
            requested_summary = {
                "name": requested_scheme.get("name_hi") if lang == "hindi_devanagari" and requested_scheme.get("name_hi") else requested_scheme.get("name", requested_scheme.get("title", "")),
                "category": requested_scheme.get("category", ""),
                "description": requested_scheme.get("description", ""),
                "benefits": requested_scheme.get("benefits", ""),
                "how_to_apply": requested_scheme.get("how_to_apply", ""),
                "documents_required": requested_scheme.get("documents_required", []),
                "eligibility_criteria": requested_scheme.get("eligibility", {}),
            }
            requested_scheme_block = f"""
REQUESTED_SCHEME_INFO:
{json.dumps(requested_summary, ensure_ascii=False, indent=2)}

REQUESTED_SCHEME_ELIGIBILITY_STATUS: {elig_result.get("status")}
REQUESTED_SCHEME_MISSING_FIELDS: {elig_result.get("missing_fields")}
"""
        else:
            requested_scheme_block = f"""
REQUESTED_SCHEME_INFO: NOT_FOUND
The user asked about "{named_query}" but this scheme does not exist in the database. Politely tell them this specific scheme isn't in your current database, then suggest 2-3 relevant alternatives from MATCHED ELIGIBLE SCHEMES DATA below if any.
"""

    convo_history = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in state["messages"])

    data_prompt = f"""CONVERSATION HISTORY SO FAR:
{convo_history}

CURRENT USER PROFILE & INTENT: {json.dumps(state['profile'])}
{requested_scheme_block}
MATCHED ELIGIBLE SCHEMES DATA:
{json.dumps(eligible_summary, ensure_ascii=False, indent=2)}

POSSIBLY ELIGIBLE SCHEMES:
{json.dumps(possibly_summary, ensure_ascii=False, indent=2)}

INSTRUCTIONS:
1. Respond to the user's latest query strictly in {lang_instruction}.
2. Provide 2-4 most relevant schemes.

Write your response to the user now:"""

    try:
        resp = llm.invoke([
            SystemMessage(content=RESPONSE_SYSTEM_PROMPT.format(lang_instruction=lang_instruction)),
            HumanMessage(content=data_prompt),
        ])
        state["reply"] = resp.content.strip()
    except Exception as e:
        logger.warning(f"generate_response: LLM call failed: {e}")
        state["reply"] = "Sorry, I'm having trouble generating a response right now. Please try again in a moment."
    return state


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("extract_info", extract_info)
    graph.add_node("ask_followup", ask_followup)
    graph.add_node("chit_chat_response", chit_chat_response)
    graph.add_node("match_schemes", match_schemes_node)
    graph.add_node("generate_response", generate_response)

    graph.set_entry_point("extract_info")
    graph.add_conditional_edges(
        "extract_info",
        route_after_extraction,
        {
            "ask_followup": "ask_followup",
            "match_schemes": "match_schemes",
            "chit_chat": "chit_chat_response",
        },
    )
    graph.add_edge("ask_followup", END)
    graph.add_edge("chit_chat_response", END)
    graph.add_edge("match_schemes", "generate_response")
    graph.add_edge("generate_response", END)

    return graph.compile()


agent_graph = build_graph()


def run_agent(messages, profile=None, language="hinglish"):
    initial_state: AgentState = {
        "messages": messages,
        "profile": profile or {},
        "language": language,
        "message_type": "new_query",
        "named_scheme_query": "",
        "matched": {"eligible": [], "possibly_eligible": []},
        "reply": "",
        "need_followup": False,
    }
    final_state = agent_graph.invoke(initial_state)
    return final_state