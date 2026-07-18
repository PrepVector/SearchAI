"""Web Research Agent — collects recent, credible web sources."""
from __future__ import annotations

from ..services import search_gateway


async def run(brief: dict, plan: dict, time_sensitive: bool) -> list[dict]:
    if not plan.get("use_web_search", True):
        return []
    queries = list(brief.get("search_queries", []))[:8]
    queries += list(plan.get("extra_official_queries", []))[:4]
    if not queries:
        return []
    results = await search_gateway.web_search(queries, per_query=5,
                                              recent=time_sensitive)
    official = [d.lower() for d in plan.get("official_domains", [])]

    def rank(r: dict) -> float:
        score = float(r.get("score") or 0)
        url = (r.get("url") or "").lower()
        if any(d in url for d in official):
            score += 5.0
        if any(t in url for t in (".gov", ".edu", "docs.", "arxiv.org",
                                  "who.int", "nature.com", "ieee.org")):
            score += 2.0
        return score

    results.sort(key=rank, reverse=True)
    return results[:24]
