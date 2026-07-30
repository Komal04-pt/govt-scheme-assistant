"""
LangGraph agent orchestration.

Flow:
  extract_info -> (missing critical info?) -> ask_followup [END]
                -> match_schemes -> generate_response [END]

The LLM is used ONLY for:
  1. extracting structured profile fields & user intent from free-form conversation
  2. writing the final natural-language explanation / answering follow-up queries
Eligibility itself is decided by eligibility.py (deterministic rules).
"""

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
    temperature=0.2, # Lower temperature for focused responses
)

CORE_FIELDS = ["occupation", "annual_income", "age", "location", "gender"]


class AgentState(TypedDict):
    messages: List[dict]          # [{"role": "user"/"assistant", "content": str}]
    profile: dict                 # extracted structured profile
    language: str                 # detected language: "hinglish" / "hindi_devanagari" / "english"
    matched: dict                 # eligible / possibly_eligible schemes
    reply: str                    # final reply text
    need_followup: bool


EXTRACTION_SYSTEM_PROMPT = """You are an information extraction assistant for a government welfare scheme eligibility checker used in India.

From the conversation so far, extract as much of the following structured profile and user intent as you can.
Only include fields you are reasonably confident about from what the user has actually said.
Do NOT guess or invent values.

Fields:
- occupation: one of ["farmer","laborer","unemployed","daily_wage","student","unorganized_sector","self_employed","govt_employee","any", or null]
- annual_income: number (in INR) or null
- age: number or null
- gender: "male" / "female" / "female_child" / null
- location: "rural" / "urban" / null
- land_owner: true / false / null
- house_owner: true / false / null
- marital_status: "widow" / "married" / "single" / null
- user_intent: list of extracted domain keywords from prompt, e.g., ["coaching", "fee_waiver", "scholarship", "education"] or []
- flags: list of applicable flags from ["income_tax_payer","govt_employee","pensioner_high","existing_lpg_connection","large_landowner","pucca_house_owner","existing_govt_pension","car_owner"] (empty list if none apply/known)

LANGUAGE DETECTION RULE (VERY IMPORTANT):
- "hinglish": User writes Hindi using Roman script / English alphabet (e.g., "Main Delhi se hu", "mujhe fee waiver chahiye").
- "hindi_devanagari": User writes using actual Devanagari script (e.g., "मैं दिल्ली से हूँ").
- "english": User writes plain English (e.g., "I am a student from Delhi").

Respond with ONLY a JSON object, no other text, in this exact format:
{
  "profile": { "occupation": null, "annual_income": null, "age": null, "gender": null,
               "location": null, "land_owner": null, "house_owner": null,
               "marital_status": null, "user_intent": [], "flags": [] },
  "language": "hinglish"
}
"""


def extract_info(state: AgentState) -> AgentState:
    convo_text = "\n".join(f"{m['role']}: {m['content']}" for m in state["messages"])
    resp = llm.invoke([
        SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
        HumanMessage(content=f"Conversation so far:\n{convo_text}\n\nExtract the profile now."),
    ])

    try:
        raw = resp.content.strip()
        # Find first '{' and last '}' to strictly isolate JSON block
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

    # Merge logic: keep previously known fields, fill in new values cleanly
    profile = dict(state.get("profile", {}))
    for k, v in new_profile.items():
        if v not in (None, [], ""):
            if k in ["user_intent", "flags"] and isinstance(v, list):
                # Merge lists without duplicating entries
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
    
    # Ask follow-up only if key profile elements are severely missing
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
        lang_fmt = "Hindi in Devanagari script"
    elif lang == "hinglish":
        lang_fmt = "Hinglish (Hindi written in Roman/English alphabet)"
    else:
        lang_fmt = "English"

    prompt = f"""The user is trying to find out which Indian government welfare schemes they qualify for.
So far we know: {json.dumps(profile)}.
We are still missing: {missing}.
Write ONE short, warm, simple follow-up question in {lang_fmt} asking for 1-2 of the missing details.
Respond with ONLY the question text, nothing else."""

    resp = llm.invoke([HumanMessage(content=prompt)])
    state["reply"] = resp.content.strip()
    return state


def match_schemes_node(state: AgentState) -> AgentState:
    state["matched"] = match_all_schemes(state["profile"])
    return state


RESPONSE_SYSTEM_PROMPT = """You are 'JanSeva AI Assistant', an empathetic, clear, and direct AI assistant helping citizens, students, and farmers in India.

STRICT LANGUAGE & SCRIPT RULES (CRITICAL):
- You MUST write the response in {lang_instruction}.
- IF THE USER IS WRITING IN HINGLISH, YOUR ENTIRE RESPONSE MUST BE IN HINGLISH (Roman Hindi).
- DO NOT USE DEVANAGARI SCRIPT AT ALL UNLESS THE USER WRITES IN DEVANAGARI SCRIPT.

STRICT SCHEME FILTERING & RELEVANCE RULES:
1. **USER INTENT & OCCUPATION STRICT MATCHING**:
   - Filter and prioritize matched schemes strictly based on the user's explicit request and occupation.
   - If user asks for "coaching", "fee waiver", "education", or is a "student", ONLY output Education, Scholarship, Youth Skill Development, or Fee Waiver schemes.
   - **STRICTLY EXCLUDE UNRELATED SCHEMES**: Do NOT show Maternity Benefits, Pension Schemes (APY), Solar Rooftop, Bank Account Opening, or Farmer schemes to a student asking for coaching/fee waiver!

2. **FALLBACK RULE (WHEN MATCHED DATA IS EMPTY)**:
   - If `MATCHED ELIGIBLE SCHEMES DATA` is empty ([]), DO NOT output generic advice like 'visit NSP portal' or 'ask your college'.
   - Instead, use domain knowledge to list exact schemes relevant to their extracted profile and intent (e.g. for a Delhi female student with income < 4L asking for coaching/fee waiver: suggest 'Delhi Higher Education Merit-cum-Means Fee Waiver Scheme', 'Jai Bhim Mukhyamantri Pratibha Vikas Yojana', and 'AICTE Pragati Scholarship for Girls'). Provide brief benefits and apply instructions for these.

3. **TONE & FORMATTING**:
   - Keep sentences clear, friendly, and structured using clean markdown bullet points.
"""


def generate_response(state: AgentState) -> AgentState:
    lang = state.get("language", "hinglish")
    
    if lang == "hindi_devanagari":
        lang_instruction = "Hindi using Devanagari script"
    elif lang == "hinglish":
        lang_instruction = "Hinglish (Hindi using Roman/English script, e.g., 'Aapke profile ke according...')"
    else:
        lang_instruction = "English"

    eligible = state["matched"].get("eligible", [])
    possibly = state["matched"].get("possibly_eligible", [])

    eligible_summary = []
    for s in eligible:
        if isinstance(s, dict):
            eligible_summary.append({
                "name": s.get("name_hi") if lang == "hindi_devanagari" else s.get("name", s.get("title", "")),
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
                "name": scheme_obj.get("name_hi") if lang == "hindi_devanagari" else scheme_obj.get("name", scheme_obj.get("title", "")),
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
1. Check the LATEST user message and user intent (`user_intent` in profile).
2. Select 2-4 MOST RELEVANT schemes from the matched list above that directly solve the user's specific query (e.g. coaching, fee waiver, education).
3. If MATCHED ELIGIBLE SCHEMES DATA is empty, execute the FALLBACK RULE in system prompt to suggest specific named schemes based on user intent and profile.
4. Output the reply strictly in {lang_instruction}.

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
    """messages: list of {"role": "user"/"assistant", "content": str}"""
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