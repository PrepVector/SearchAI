"""Research Director — one agent replacing understanding + enhancer + planner.

A single structured call that decodes the query, writes the research brief,
and plans retrieval. Fewer hops, one coherent view of the task.
"""
from __future__ import annotations

import json
from datetime import date

from ..services.llm_gateway import chat_json

SYSTEM = """You are the Research Director inside SEARCH AI, a premium
multi-model research system. In ONE pass, analyse the searched topic, write
the research brief, and plan retrieval. Never answer the topic itself.
The current year is {year}. Return JSON with EXACTLY this shape:

{{"analysis": {{
  "normalized_topic": "clean unambiguous restatement",
  "query_lock": "the one question this article is contractually obliged to
     answer — any paragraph not serving it is drift",
  "adjacent_topics_to_avoid": ["3-6 neighbouring subjects that would be drift"],
  "domain": "ai_ml | mathematics_statistics | cybersecurity | software_systems |
     finance_economics | medicine_healthcare | law_policy | history_society |
     physics_engineering | chemistry_biology | environment_geography |
     education_business | general",
  "subdomain": "specific field",
  "intent": "what | why | how | comparison | decision | latest_current |
     implementation | research_overview | mathematical_explanation",
  "audience": "who realistically asks this and what they know",
  "expected_answer_type": "what a satisfying answer must contain",
  "is_time_sensitive": true/false,
  "key_entities": ["named entities, products, models, laws, theorems"],
  "ambiguities": []}},
 "brief": {{
  "research_prompt": "4-6 sentence expanded prompt naming exact mechanisms,
     quantities, entities and boundaries",
  "answer_contract": ["4-7 checkable obligations the article must deliver"],
  "out_of_scope": ["adjacent themes to exclude"],
  "research_questions": ["6-9 sharp domain-specific questions"],
  "search_queries": ["8-11 short keyword queries spanning THREE horizons:
     foundational/seminal, current {year} state + official docs,
     forward-looking open problems / roadmap"],
  "academic_queries": ["4-5 scholarly phrases: at least one seminal-work
     query and one recent-survey query"],
  "visual_queries": ["6-9 image queries returning explanatory
     diagrams/graphs/figures for THIS exact topic, never generic imagery"],
  "validation_criteria": ["5-7 concrete checks about THIS topic's facts"]}},
 "plan": {{
  "use_web_search": true/false,
  "use_academic_search": true/false,
  "verify_currentness": true/false,
  "official_domains": ["official domains for this topic's entities"],
  "extra_official_queries": ["0-4 official-docs-targeted queries"],
  "priority_note": "one sentence on retrieval strategy"}}
}}

is_time_sensitive MUST be true when the topic involves latest/current/newest,
prices, versions, model names, laws, rankings, releases, or anything whose
true value changes over time; verify_currentness follows it."""


async def run(topic: str, options: dict) -> dict:
    year = date.today().year
    user = (f"Searched topic:\n\"\"\"{topic}\"\"\"\n"
            f"User toggles: web_research={options.get('web_research', True)}, "
            f"current_findings={options.get('current_findings', True)}.")
    out = await chat_json("research", SYSTEM.format(year=year), user,
                          max_tokens=3200, temperature=0.3)
    analysis = out.get("analysis") or {}
    brief = out.get("brief") or {}
    plan = out.get("plan") or {}
    # user toggles are law
    if not options.get("web_research", True):
        plan["use_web_search"] = False
    if not options.get("current_findings", True):
        plan["verify_currentness"] = False
    elif analysis.get("is_time_sensitive"):
        plan["verify_currentness"] = True
    plan.setdefault("use_web_search", True)
    plan.setdefault("use_academic_search", True)
    return {"analysis": analysis, "brief": brief, "plan": plan}
