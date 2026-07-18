"""Visual Reference Agent — topic-family image intelligence.

Finds referential images that *explain* the topic (graphs, diagrams, charts,
schematics), never random stock imagery. Candidates are scored by an LLM for
topic linkage + explanatory value before acceptance.
"""
from __future__ import annotations

import json

from ..config import get_settings
from ..services import search_gateway
from ..services.llm_gateway import chat_json

# Topic-family preferred visual archetypes (drives query expansion + scoring)
FAMILY_VISUALS: dict[str, list[str]] = {
    "ai_ml": ["architecture diagram", "workflow pipeline",
              "training vs validation loss graph", "ROC curve",
              "confusion matrix", "benchmark comparison chart",
              "decision boundary plot", "bias variance tradeoff graph"],
    "mathematics_statistics": ["PMF plot", "CDF plot",
                               "probability distribution graph", "histogram",
                               "formula figure", "worked example diagram"],
    "cybersecurity": ["attack flow diagram", "threat model diagram",
                      "SOC workflow", "detection pipeline diagram",
                      "IDS IPS architecture", "MITRE ATT&CK path diagram",
                      "confusion matrix detection"],
    "medicine_healthcare": ["pathway diagram", "mechanism of action chart",
                            "anatomy figure", "clinical workflow diagram",
                            "diagnosis treatment flowchart"],
    "chemistry_biology": ["pathway diagram", "molecular structure figure",
                          "reaction mechanism diagram", "cell process figure"],
    "finance_economics": ["time series chart", "risk return diagram",
                          "market cycle figure", "balance sheet diagram",
                          "economic flow chart"],
    "history_society": ["timeline", "historical map",
                        "cause effect diagram", "actor relationship chart"],
    "environment_geography": ["map", "cycle diagram", "impact chart",
                              "satellite image", "ecological process figure"],
    "physics_engineering": ["schematic", "block diagram", "circuit diagram",
                            "formula graph", "system architecture diagram"],
    "software_systems": ["system architecture diagram", "API workflow diagram",
                         "sequence diagram", "deployment topology diagram"],
    "law_policy": ["process flowchart", "jurisdiction map",
                   "compliance workflow diagram", "timeline"],
    "education_business": ["framework diagram", "process flowchart",
                           "comparison chart", "org structure diagram"],
    "general": ["explanatory diagram", "process flowchart",
                "comparison chart", "timeline"],
}

SCORE_SYSTEM = """You are the Visual Relevance Judge inside SEARCH AI.
For each candidate image (title + source + originating query) decide whether
it would genuinely EXPLAIN the topic to a reader — a graph, diagram, chart,
figure, map, timeline, workflow, schematic, formula plot, benchmark chart,
official screenshot, academic figure or documentation diagram about THIS topic.

Reject: logos, stock photos, decorative art, memes, book covers, unrelated
subjects, and images that merely come from a trusted site without explaining
the topic. Trusted origin alone is NOT acceptance grounds. Return JSON:

{"accepted": [{"i": index, "score": 0-10,
   "caption": "specific caption naming what the figure shows about the topic",
   "explanation": "1-2 sentence reader-facing explanation of the figure",
   "section_hint": "which article section this best supports"}]}
Official documentation screenshots, README/architecture diagrams and
academic figures about the topic count as explanatory. Only include
candidates scoring 6 or above (a genuine explanatory figure or
documentation screenshot at modest resolution IS a 6 — do not
reject real figures for polish alone); return the best ones up to the stated
maximum. Never accept two candidates that appear to be the same figure."""


def _i(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def build_visual_queries(topic: str, domain: str, brief: dict) -> list[str]:
    queries = list(brief.get("visual_queries", []))[:8]
    fam = FAMILY_VISUALS.get(domain, FAMILY_VISUALS["general"])
    head = topic if len(topic) < 60 else topic[:60]
    for archetype in fam[:4]:
        q = f"{head} {archetype}"
        if q not in queries:
            queries.append(q)
    return queries[:10]


async def run(topic: str, domain: str, brief: dict,
              outline_titles: list[str], need: int) -> list[dict]:
    s = get_settings()
    if not s.enable_referential_images or need <= 0:
        return []
    queries = build_visual_queries(topic, domain, brief)
    per_query = 6 if s.enable_deep_image_search else 3
    candidates = await search_gateway.image_search(queries, per_query=per_query)
    candidates = candidates[:s.max_visual_references]
    if not candidates:
        return []

    view = [{"i": i, "title": c.get("title", "")[:120],
             "source": c.get("source", "")[:60],
             "page": c.get("page", "")[:120],
             "query": c.get("query", "")[:80],
             "size": f"{c.get('width', 0)}x{c.get('height', 0)}"}
            for i, c in enumerate(candidates)]
    user = (f"Topic: {topic}\nDomain family: {domain}\n"
            f"Article sections: {json.dumps(outline_titles)}\n"
            f"Images needed: {need} (accept up to {need * 2} so weaker links "
            f"have verified spares)\n\nCANDIDATES:\n"
            f"{json.dumps(view, ensure_ascii=False)}")
    try:
        verdict = await chat_json("validator", SCORE_SYSTEM, user,
                                  max_tokens=1800, temperature=0.1)
    except Exception:
        verdict = {"accepted": []}

    accepted = []
    seen_urls: set[str] = set()
    for a in sorted(verdict.get("accepted", []) or [],
                    key=lambda x: -_f(x.get("score", 0))):
        i = _i(a.get("i"))
        if i is None or not (0 <= i < len(candidates)):
            continue
        c = candidates[i]
        if c["url"] in seen_urls:
            continue
        # discard tiny thumbnails — unreadable in the article
        if (c.get("width") or 0) and (c.get("width") or 0) < 320:
            continue
        seen_urls.add(c["url"])
        accepted.append({
            "url": c["url"], "thumbnail": c.get("thumbnail", c["url"]),
            "caption": a.get("caption", c.get("title", topic))[:220],
            "explanation": a.get("explanation", "")[:400],
            "source_label": c.get("source") or c.get("engine", "web"),
            "page": c.get("page", ""),
            "section_hint": a.get("section_hint", ""),
            "score": a.get("score", 6),
        })
        if len(accepted) >= need * 2:
            break
    return accepted
