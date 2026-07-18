"""Source Credibility Agent — removes irrelevant, weak or drifting sources."""
from __future__ import annotations

import json

from ..services.llm_gateway import chat_json

SYSTEM = """You are the Source Credibility Agent inside SEARCH AI. You receive
candidate web sources and academic papers for a topic. Keep ONLY sources that
directly support THIS exact topic. Remove:
- irrelevant or off-topic results,
- papers about a different subject that share keywords,
- broad domain overviews that never touch the specific topic,
- SEO listicles and low-signal aggregator pages when better sources exist.
For current product/model/law questions, official documentation outranks
everything else. FABRICATION RISK — drop sources whose central claims are products,
tools, plugins, marketplaces, "skills" or statistics that no official or
first-party source in the set corroborates: throwaway repos, SEO content
farms, affiliate pages and invented-sounding directories are the classic
carriers. A single uncorroborated source is not evidence a product
exists. Note such drops in dropped_reasons as "fabrication risk".

Return JSON:

{
 "kept_web": [indices of web sources to keep, best first],
 "kept_papers": [indices of papers to keep, best first],
 "dropped_reasons": ["short reasons for notable drops, max 5"],
 "credibility_note": "one sentence overall verdict on evidence quality"
}"""


async def run(topic: str, web: list[dict], papers: list[dict],
              time_sensitive: bool) -> dict:
    if not web and not papers:
        return {"kept_web": [], "kept_papers": [], "dropped_reasons": [],
                "credibility_note": "No external sources retrieved."}
    web_view = [{"i": i, "title": r.get("title", "")[:140],
                 "url": r.get("url", "")[:160],
                 "snippet": r.get("snippet", "")[:280]}
                for i, r in enumerate(web[:24])]
    paper_view = [{"i": i, "title": p.get("title", "")[:160],
                   "year": p.get("year"), "cited_by": p.get("cited_by"),
                   "abstract": p.get("abstract", "")[:240]}
                  for i, p in enumerate(papers[:18])]
    user = (f"Topic: {topic}\nTime-sensitive: {time_sensitive}\n\n"
            f"WEB SOURCES:\n{json.dumps(web_view, ensure_ascii=False)}\n\n"
            f"PAPERS:\n{json.dumps(paper_view, ensure_ascii=False)}")
    verdict = await chat_json("validator", SYSTEM, user,
                              max_tokens=1200, temperature=0.1)
    def _i(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    kw = [_i(i) for i in verdict.get("kept_web", []) or []]
    kp = [_i(i) for i in verdict.get("kept_papers", []) or []]
    kept_web = [web[i] for i in kw if i is not None and 0 <= i < len(web)]
    kept_papers = [papers[i] for i in kp
                   if i is not None and 0 <= i < len(papers)]
    return {"web": kept_web[:14], "papers": kept_papers[:10],
            "dropped_reasons": verdict.get("dropped_reasons", []),
            "credibility_note": verdict.get("credibility_note", "")}
