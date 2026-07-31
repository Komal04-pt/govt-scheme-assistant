import os
import json
import re
from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from eligibility import match_all_schemes

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model="llama-3.3-70b-versatile",
    temperature=0.2,
)

CORE_FIELDS = ["occupation", "annual_income", "age", "location", "gender"]


class AgentState(TypedDict):
    messages: List[dict]          
    profile: dict                 
    language: str                 
    matched: dict                 
    reply: str                    
    need_followup: bool


EXTRACTION_SYSTEM_PROMPT = """You are an information extraction assistant for a government welfare scheme eligibility checker in India.

Extract structured profile information and detect user language preference accurately.

DYNAMIC LANGUAGE DETECTION RULES:
Analyze the LATEST user message carefully:
1. "english": User writes in standard English (e.g., "Tell me about schemes", "I am a student") OR explicitly requests English ("in English").
2. "hindi_devanagari": User writes using actual Devanagari script (e.g. "मुझे योजना बताओ", "हिंदी में लिखो") OR explicitly requests Hindi/Devanagari ("Hindi me likho", "in Hindi").
3. "hinglish": User writes Hindi using Roman/English letters (e.g. "mujhe schemes batayein", "main student hu") OR explicitly requests Hinglish ("Hinglish me batao").

Respond with ONLY a JSON object:
{
  "profile": { "occupation": null, "annual_income": null, "age": null, "gender": null,
               "location": null, "land_owner": null, "house_owner": null,
               "marital_status": null, "user_intent": [], "flags": [] },
  "language": "english"
}
"""


def extract_info(state: AgentState) -> AgentState:
    convo_text = "\n".join(f"{m['role']}: {m['content']}" for m in state["messages"])
    resp = llm.invoke([
        SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
        HumanMessage(content=f"Conversation history:\n{convo_text}\n\nExtract profile & language preference now."),
    ])

    try:
        raw = resp.content.strip()
        start_idx = raw.find('{')
        end_idx = raw.rfind('}')
        if start_idx != -1 and end_idx != -1:
            raw = raw[start_idx:end_idx+1]
        
        parsed = json.loads(raw)
        new_profile = parsed.get("profile", {})
        language = parsed.get("language", "hinglish")
    except Exception:
        new_profile = {}
        language = state.get("language", "hinglish")

    if state["messages"]:
        last_msg = state["messages"][-1]["content"].lower()
        if "hinglish" in last_msg:
            language = "hinglish"
        elif any(k in last_msg for k in ["हिंदी", "hindi", "देवनागरी"]):
            language = "hindi_devanagari"
        elif any(k in last_msg for k in ["in english", "english please", "speak in english"]):
            language = "english"

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
    return state


def check_missing_core(state: AgentState) -> str:
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

    resp = llm.invoke([HumanMessage(content=prompt)])
    state["reply"] = resp.content.strip()
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
2. **FALLBACK RULE**:
   - If `MATCHED ELIGIBLE SCHEMES DATA` is empty, suggest domain-specific schemes relevant to user profile.
3. **FORMATTING**: Use clear markdown bullet points.
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

    convo_history = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in state["messages"])

    data_prompt = f"""CONVERSATION HISTORY SO FAR:
{convo_history}

CURRENT USER PROFILE & INTENT: {json.dumps(state['profile'])}

MATCHED ELIGIBLE SCHEMES DATA:
{json.dumps(eligible_summary, ensure_ascii=False, indent=2)}

POSSIBLY ELIGIBLE SCHEMES:
{json.dumps(possibly_summary, ensure_ascii=False, indent=2)}

INSTRUCTIONS:
1. Respond to the user's latest query strictly in {lang_instruction}.
2. Provide 2-4 most relevant schemes.

Write your response to the user now:"""

    resp = llm.invoke([
        SystemMessage(content=RESPONSE_SYSTEM_PROMPT.format(lang_instruction=lang_instruction)),
        HumanMessage(content=data_prompt),
    ])
    state["reply"] = resp.content.strip()
    return state


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("extract_info", extract_info)
    graph.add_node("ask_followup", ask_followup)
    graph.add_node("match_schemes", match_schemes_node)
    graph.add_node("generate_response", generate_response)

    graph.set_entry_point("extract_info")
    graph.add_conditional_edges(
        "extract_info",
        check_missing_core,
        {"ask_followup": "ask_followup", "match_schemes": "match_schemes"},
    )
    graph.add_edge("ask_followup", END)
    graph.add_edge("match_schemes", "generate_response")
    graph.add_edge("generate_response", END)

    return graph.compile()


agent_graph = build_graph()


def run_agent(messages, profile=None, language="hinglish"):
    initial_state: AgentState = {
        "messages": messages,
        "profile": profile or {},
        "language": language,
        "matched": {"eligible": [], "possibly_eligible": []},
        "reply": "",
        "need_followup": False,
    }
    final_state = agent_graph.invoke(initial_state)
    return final_state