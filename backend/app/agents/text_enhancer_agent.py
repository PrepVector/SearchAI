"""Scholarly Polish & Repair — markdown-native single editorial pass.

Absorbs the former enhancer, humanizer, and domain-versatility agents.
Reads and writes the same delimited-markdown format as the writer, so the
editor also escapes the JSON tax and benefits from extended thinking.
"""
from __future__ import annotations

import json

from ..services.llm_gateway import LLMError, chat
from .article_writer_agent import parse_article_md, serialize_article_md

FIELD_STANDARDS = {
    "mathematics_statistics": "formulas, notation, assumptions, worked examples, properties",
    "ai_ml": "datasets, features, model, training, validation, metrics, baselines, failure modes",
    "cybersecurity": "threat model, attack path, indicators, detection, prevention, incident response, false positives",
    "finance_economics": "risk, metrics, regulation, cost, governance, trade-offs",
    "history_society": "timeline, actors, causes, context, consequences, interpretations",
    "medicine_healthcare": "mechanisms, symptoms, diagnosis, evidence, risks, limitations",
    "law_policy": "jurisdiction, procedure, documents, compliance, legal boundaries",
    "software_systems": "architecture, workflow, code, testing, deployment, monitoring",
    "physics_engineering": "governing equations, assumptions, system diagrams, tolerances, failure analysis",
    "chemistry_biology": "mechanisms, structures, pathways, experimental evidence, limitations",
    "environment_geography": "processes, spatial context, data, impacts, uncertainty",
    "education_business": "frameworks, evidence, implementation, metrics, trade-offs",
    "general": "clear mechanism, concrete examples, evidence, limitations",
}

POLISH_SYSTEM = """You are the Scholarly Polish editor inside SEARCH AI —
one pass doing the work of three editors on the draft article:
1. FIELD STANDARDS — hold every section to expert standard for the field
   ({standards}); strengthen thin passages with missing mechanisms,
   quantities, named methods and adjudication of competing views.
2. CLARITY — tighten repetition, fix transitions, sharpen weak passages.
3. HUMAN VOICE — remove robotic patterns; senior-scholar rhythm; never
   dumb down terminology or numbers.
4. COHESION — one argument on the narrative thread: every section after
   the first opens by advancing from the previous section's endpoint
   (repair cold openings organically, never "as discussed above"); one
   term per concept throughout; deepen the single thinnest section by one
   full rung (claim -> mechanism -> quantification -> implication).
HARD RULES: exact same SECTION blocks — same ids, same titles, same order,
none added or removed; every sentence must serve the searched query;
preserve all [S#]/[P#]/[F#] markers, LaTeX, tables and code; keep the
historic -> current -> future arc; no length inflation.
If REPAIR NOTES are supplied they are top priority: rewrite exactly the
flagged sections to re-anchor on the query and add the missing answer
elements; touch other sections only lightly.
OUTPUT: the FULL article in the exact same delimited format you received
(=== TITLE === ... === SECTION: id | title === ...). No JSON, no
commentary before or after."""


async def polish(article: dict, topic: str, domain: str,
                 standards: str = "", thread: str = "",
                 repair_notes: dict | None = None,
                 role: str = "editor") -> dict:
    standards = standards or FIELD_STANDARDS.get(domain,
                                                 FIELD_STANDARDS["general"])
    repair = ""
    if repair_notes:
        repair = ("\n\nREPAIR NOTES (top priority):\n"
                  + json.dumps(repair_notes, ensure_ascii=False))
    user = (f"Searched query: {topic}\nDomain: {domain}\n"
            f"Narrative thread: {thread}{repair}\n\n"
            f"DRAFT ARTICLE:\n{serialize_article_md(article)}")
    raw = await chat(role, POLISH_SYSTEM.format(standards=standards), user,
                     max_tokens=9000, temperature=0.5, thinking=True)
    out = parse_article_md(raw)
    if not out["sections"]:
        raise LLMError("Polish pass returned no sections.")
    return out


# Back-compat aliases used by the pipeline's repair loop
async def run(article: dict, topic: str, repair_notes: dict | None = None,
              role: str = "editor") -> dict:
    return await polish(article, topic, "general", thread="",
                        repair_notes=repair_notes, role=role)
