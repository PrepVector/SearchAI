"""Search gateway — web, academic and image retrieval behind one interface.

Web:     Tavily -> Exa -> SerpAPI (whichever keys exist, merged + deduped)
Academic: OpenAlex + Crossref (keyless; polite-pool emails from .env)
Images:  SerpAPI Google Images -> Openverse -> Wikimedia Commons
"""
from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import quote

import httpx

from ..config import get_settings


async def _get(client: httpx.AsyncClient, url: str, **kw) -> Any:
    r = await client.get(url, **kw)
    r.raise_for_status()
    return r.json()


async def _post(client: httpx.AsyncClient, url: str, **kw) -> Any:
    r = await client.post(url, **kw)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------- web search
async def tavily_search(query: str, max_results: int = 6,
                        recent: bool = False) -> list[dict]:
    s = get_settings()
    if not s.tavily_api_key:
        return []
    payload = {"api_key": s.tavily_api_key, "query": query,
               "max_results": max_results, "search_depth": "advanced",
               "include_answer": False}
    if recent:
        payload["days"] = 365
        payload["topic"] = "news" if any(
            w in query.lower() for w in ("news", "announce", "release")) else "general"
    try:
        async with httpx.AsyncClient(timeout=s.search_timeout) as c:
            data = await _post(c, "https://api.tavily.com/search", json=payload)
        return [{"title": r.get("title", ""), "url": r.get("url", ""),
                 "snippet": (r.get("content") or "")[:1200],
                 "published": r.get("published_date", ""),
                 "engine": "tavily", "score": r.get("score", 0)}
                for r in data.get("results", [])]
    except Exception:
        return []


async def exa_search(query: str, max_results: int = 6) -> list[dict]:
    s = get_settings()
    if not s.exa_api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=s.search_timeout) as c:
            data = await _post(
                c, "https://api.exa.ai/search",
                headers={"x-api-key": s.exa_api_key},
                json={"query": query, "numResults": max_results,
                      "contents": {"text": {"maxCharacters": 1200}}})
        return [{"title": r.get("title", ""), "url": r.get("url", ""),
                 "snippet": (r.get("text") or "")[:1200],
                 "published": r.get("publishedDate", ""),
                 "engine": "exa", "score": r.get("score", 0)}
                for r in data.get("results", [])]
    except Exception:
        return []


async def serpapi_search(query: str, max_results: int = 6) -> list[dict]:
    s = get_settings()
    if not s.serpapi_api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=s.search_timeout) as c:
            data = await _get(c, "https://serpapi.com/search.json",
                              params={"engine": "google", "q": query,
                                      "num": max_results,
                                      "api_key": s.serpapi_api_key})
        return [{"title": r.get("title", ""), "url": r.get("link", ""),
                 "snippet": (r.get("snippet") or "")[:1200],
                 "published": r.get("date", ""), "engine": "serpapi",
                 "score": 0}
                for r in data.get("organic_results", [])[:max_results]]
    except Exception:
        return []


async def web_search(queries: list[str], per_query: int = 5,
                     recent: bool = False) -> list[dict]:
    tasks = []
    for q in queries[:8]:
        tasks.append(tavily_search(q, per_query, recent))
        tasks.append(exa_search(q, per_query))
        tasks.append(serpapi_search(q, per_query))
    batches = await asyncio.gather(*tasks)
    seen: set[str] = set()
    out: list[dict] = []
    for batch in batches:
        for r in batch:
            url = (r.get("url") or "").split("#")[0].rstrip("/")
            if url and url not in seen:
                seen.add(url)
                out.append(r)
    return out


# ------------------------------------------------------------ academic search
async def openalex_search(query: str, max_results: int = 8) -> list[dict]:
    s = get_settings()
    params = {"search": query, "per-page": max_results,
              "sort": "relevance_score:desc"}
    if s.openalex_email:
        params["mailto"] = s.openalex_email
    try:
        async with httpx.AsyncClient(timeout=s.search_timeout) as c:
            data = await _get(c, "https://api.openalex.org/works", params=params)
        out = []
        for w in data.get("results", []):
            abstract = ""
            inv = w.get("abstract_inverted_index")
            if inv:
                pos: dict[int, str] = {}
                for word, idxs in inv.items():
                    for i in idxs:
                        pos[i] = word
                abstract = " ".join(pos[i] for i in sorted(pos))[:1400]
            out.append({
                "title": w.get("display_name", ""),
                "url": (w.get("primary_location") or {}).get("landing_page_url", "")
                       or w.get("id", ""),
                "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
                "year": w.get("publication_year"),
                "abstract": abstract,
                "cited_by": w.get("cited_by_count", 0),
                "engine": "openalex",
            })
        return out
    except Exception:
        return []


async def crossref_search(query: str, max_results: int = 8) -> list[dict]:
    s = get_settings()
    params: dict[str, Any] = {"query": query, "rows": max_results}
    if s.crossref_email:
        params["mailto"] = s.crossref_email
    try:
        async with httpx.AsyncClient(timeout=s.search_timeout) as c:
            data = await _get(c, "https://api.crossref.org/works", params=params)
        out = []
        for it in data.get("message", {}).get("items", []):
            year = None
            parts = (it.get("issued") or {}).get("date-parts") or []
            if parts and parts[0]:
                year = parts[0][0]
            out.append({
                "title": " ".join(it.get("title") or [])[:300],
                "url": it.get("URL", ""),
                "doi": it.get("DOI", ""),
                "year": year,
                "abstract": (it.get("abstract") or "")[:1400],
                "cited_by": it.get("is-referenced-by-count", 0),
                "engine": "crossref",
            })
        return out
    except Exception:
        return []


async def academic_search(queries: list[str], per_query: int = 6) -> list[dict]:
    tasks = []
    for q in queries[:5]:
        tasks.append(openalex_search(q, per_query))
        tasks.append(crossref_search(q, per_query))
    batches = await asyncio.gather(*tasks)
    seen: set[str] = set()
    out: list[dict] = []
    for batch in batches:
        for p in batch:
            key = p.get("doi") or p.get("title", "").lower()
            if key and key not in seen:
                seen.add(key)
                out.append(p)
    return out


# --------------------------------------------------------------- image search
async def serpapi_images(query: str, max_results: int = 8) -> list[dict]:
    s = get_settings()
    if not s.serpapi_api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=s.search_timeout) as c:
            data = await _get(c, "https://serpapi.com/search.json",
                              params={"engine": "google_images", "q": query,
                                      "api_key": s.serpapi_api_key})
        return [{"url": r.get("original", ""),
                 "thumbnail": r.get("thumbnail", ""),
                 "title": r.get("title", ""),
                 "page": r.get("link", ""),
                 "source": r.get("source", ""), "engine": "serpapi_images",
                 "width": r.get("original_width", 0),
                 "height": r.get("original_height", 0)}
                for r in data.get("images_results", [])[:max_results]
                if r.get("original")]
    except Exception:
        return []


async def openverse_images(query: str, max_results: int = 8) -> list[dict]:
    s = get_settings()
    try:
        async with httpx.AsyncClient(timeout=s.search_timeout) as c:
            data = await _get(c, "https://api.openverse.org/v1/images/",
                              params={"q": query, "page_size": max_results},
                              headers={"User-Agent": "SEARCH-AI/1.0"})
        return [{"url": r.get("url", ""), "thumbnail": r.get("thumbnail", ""),
                 "title": r.get("title", ""),
                 "page": r.get("foreign_landing_url", ""),
                 "source": r.get("source", "openverse"),
                 "engine": "openverse",
                 "width": r.get("width") or 0, "height": r.get("height") or 0}
                for r in data.get("results", []) if r.get("url")]
    except Exception:
        return []


async def wikimedia_images(query: str, max_results: int = 8) -> list[dict]:
    s = get_settings()
    url = ("https://commons.wikimedia.org/w/api.php?action=query&format=json"
           "&generator=search&gsrnamespace=6&gsrlimit=" + str(max_results) +
           "&gsrsearch=" + quote(query) +
           "&prop=imageinfo&iiprop=url|size|extmetadata&iiurlwidth=1200")
    try:
        async with httpx.AsyncClient(timeout=s.search_timeout) as c:
            data = await _get(c, url, headers={"User-Agent": "SEARCH-AI/1.0"})
        out = []
        for page in (data.get("query", {}).get("pages") or {}).values():
            info = (page.get("imageinfo") or [{}])[0]
            u = info.get("thumburl") or info.get("url", "")
            if not u or u.lower().endswith((".ogg", ".webm", ".pdf", ".tif")):
                continue
            out.append({"url": u, "thumbnail": info.get("thumburl", u),
                        "title": page.get("title", "").replace("File:", ""),
                        "page": info.get("descriptionurl", ""),
                        "source": "Wikimedia Commons", "engine": "wikimedia",
                        "width": info.get("thumbwidth") or info.get("width", 0),
                        "height": info.get("thumbheight") or info.get("height", 0)})
        return out
    except Exception:
        return []


async def image_search(queries: list[str], per_query: int = 6) -> list[dict]:
    tasks = []
    for q in queries[:10]:
        tasks.append(serpapi_images(q, per_query))
        tasks.append(openverse_images(q, per_query))
        tasks.append(wikimedia_images(q, per_query))
    batches = await asyncio.gather(*tasks)
    seen: set[str] = set()
    out: list[dict] = []
    for i, batch in enumerate(batches):
        for r in batch:
            u = r.get("url", "")
            if u and u not in seen:
                seen.add(u)
                r["query"] = queries[min(i // 3, len(queries) - 1)] if queries else ""
                out.append(r)
    return out
