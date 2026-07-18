"""Academic Research Agent — OpenAlex + Crossref paper retrieval."""
from __future__ import annotations

from ..services import search_gateway


async def run(brief: dict, plan: dict) -> list[dict]:
    if not plan.get("use_academic_search", True):
        return []
    queries = list(brief.get("academic_queries", []))[:5]
    if not queries:
        return []
    papers = await search_gateway.academic_search(queries, per_query=6)
    # Blend the literature across time: the most-cited (seminal/foundational)
    # papers AND the most recent publications, so the writer can build a
    # proper historic -> state-of-the-art arc instead of citing one era.
    by_citations = sorted(papers, key=lambda p: (p.get("cited_by") or 0),
                          reverse=True)
    by_year = sorted(papers, key=lambda p: (p.get("year") or 0), reverse=True)
    merged: list[dict] = []
    seen: set[str] = set()
    for p in by_citations[:12] + by_year[:8]:
        key = p.get("doi") or (p.get("title") or "").lower()
        if key and key not in seen:
            seen.add(key)
            merged.append(p)
    return merged[:18]
