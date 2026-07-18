"""Final Formatter Agent — assembles the publish-ready article object."""
from __future__ import annotations

import re


_PLACEHOLDER = re.compile(r"@@MATH\d+@@|@@TBL\d+@@|@@CODE\d+@@")


_REF_HEADING = re.compile(
    r"^#{1,6}\s*(?:\d+[.)]\s*)?(references|bibliography|sources|works cited)\b.*$",
    re.IGNORECASE | re.MULTILINE)


def strip_model_references(text: str) -> str:
    """Writers must not emit their own reference lists (the pipeline builds
    references from evidence). Cut any such trailing block."""
    m = _REF_HEADING.search(text)
    if m and m.start() > len(text) * 0.3:
        return text[:m.start()].rstrip()
    return text


def scrub(text: str) -> str:
    """Remove any leaked internal placeholders and stray artifacts."""
    text = _PLACEHOLDER.sub("", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


_CITE = re.compile(r"\[\s*((?:[SPF]\s*\d+)(?:\s*,\s*[SPF]?\s*\d+)*)\s*\]")


def _rewrite_citations(text: str, marker_map: dict[str, int]) -> str:
    """Turn writer evidence markers ([S3], [P4, P5], [F2]) into numbered
    citation tokens ⟦4,5⟧ that map to the References list. Unmapped
    markers are dropped rather than shown raw."""
    def sub(m):
        nums: list[str] = []
        last_letter = "S"
        for tok in m.group(1).split(","):
            tok = tok.strip().upper().replace(" ", "")
            if tok and tok[0] in "SPF":
                last_letter, digits = tok[0], tok[1:]
            else:
                digits = tok
            if not digits.isdigit():
                continue
            n = marker_map.get(f"{last_letter}{digits}")
            if n and str(n) not in nums:
                nums.append(str(n))
        # Inline citation display is disabled by user preference — the
        # grounding still shapes the References list; markers just vanish.
        return ""
    out = _CITE.sub(sub, text)
    out = re.sub(r"[ \t]+([.,;:)])", r"\1", out)
    return re.sub(r"(?<=\S) {2,}(?=\S)", " ", out)


def assemble(topic: str, outline: dict, article: dict, images: list[dict],
             evidence: dict, fact_sheet: list[dict] | None = None) -> dict:
    sections = []
    for sec in article.get("sections", []):
        sections.append({
            "id": sec.get("id", ""),
            "title": scrub(sec.get("title", "")),
            "markdown": strip_model_references(scrub(sec.get("markdown", ""))),
            "pull_quote": sec.get("pull_quote"),
        })

    references = []
    by_key: dict[str, int] = {}
    marker_map: dict[str, int] = {}

    def _add(key: str, entry: dict) -> int:
        if key in by_key:
            return by_key[key]
        references.append(entry)
        by_key[key] = len(references)
        return by_key[key]

    for i, r in enumerate(evidence.get("web", [])[:14]):
        key = (r.get("url") or "").split("#")[0].rstrip("/")
        if not key:
            continue
        n = _add(key, {"title": r.get("title", "")[:200] or key, "url": key,
                       "source": r.get("engine", "web"), "year": None,
                       "doi": ""})
        marker_map[f"S{i+1}"] = n
    for i, p in enumerate(evidence.get("papers", [])[:10]):
        key = (p.get("doi") or p.get("url") or p.get("title", "")).rstrip("/")
        if not key:
            continue
        n = _add(key, {"title": p.get("title", "")[:200],
                       "url": p.get("url", ""),
                       "source": p.get("engine", "academic"),
                       "year": p.get("year"), "doi": p.get("doi", "")})
        marker_map[f"P{i+1}"] = n
    for i, f in enumerate(fact_sheet or []):
        key = (f.get("source_url") or "").split("#")[0].rstrip("/")
        if not key:
            continue
        n = _add(key, {"title": f.get("source_title", "")[:200] or key,
                       "url": key, "source": "official", "year": None,
                       "doi": ""})
        marker_map[f"F{i+1}"] = n

    for sec in sections:
        sec["markdown"] = _rewrite_citations(sec["markdown"], marker_map)
        if sec.get("pull_quote"):
            sec["pull_quote"] = re.sub(r"⟦[^⟧]*⟧", "", _rewrite_citations(
                sec["pull_quote"], marker_map)).strip()

    return {
        "topic": topic,
        "title": scrub(article.get("title") or outline.get("title") or topic),
        "layout": outline.get("layout", "research_paper"),
        "abstract": _rewrite_citations(scrub(article.get("abstract", "")),
                                        marker_map),
        "key_takeaways": [
            _rewrite_citations(scrub(str(k)), marker_map)
            for k in (article.get("key_takeaways") or [])
            if str(k).strip()][:7],
        "executive_answer": _rewrite_citations(
            scrub(article.get("executive_answer", "")), marker_map),
        "sections": sections,
        "images": images,
        "references": references,
    }
