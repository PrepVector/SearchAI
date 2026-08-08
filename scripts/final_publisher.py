#!/usr/bin/env python3
"""final-publisher — assembles the publish-ready article object. Fully
deterministic (no model call): scrubs stray placeholders and any
model-written reference list, maps evidence markers to a deduplicated
References list, attaches images and takeaways.

Usage:
  python3 final_publisher.py assemble <topic.txt> <outline.json> <article.json> \
      <images.json> <evidence.json> <fact_sheet.json> <evidence_map.json> <out.json>

<evidence_map.json> is evidence-mapper's own output (the file with the
"E1"/"E2"/... claim ids) — either the full {"evidence": [...]} wrapper or
a bare list. Pass evidence_map.json itself; there's no need to reshape it
first the way <evidence.json>/<fact_sheet.json> require.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from _jsonio import read_json, write_json, usage

_PLACEHOLDER = re.compile(r"@@MATH\d+@@|@@TBL\d+@@|@@CODE\d+@@")
_REF_HEADING = re.compile(
    r"^#{1,6}\s*(?:\d+[.)]\s*)?(references|bibliography|sources|works cited)\b.*$",
    re.IGNORECASE | re.MULTILINE)
_CITE = re.compile(r"\[\s*((?:[SPFE]\s*\d+)(?:\s*,\s*[SPFE]?\s*\d+)*)\s*\]")


def strip_model_references(text: str) -> str:
    m = _REF_HEADING.search(text)
    if m and m.start() > len(text) * 0.3:
        return text[:m.start()].rstrip()
    return text


def scrub(text: str) -> str:
    text = _PLACEHOLDER.sub("", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def _rewrite_citations(text: str, marker_map: dict[str, int]) -> str:
    """[E#] is evidence-mapper's own claim numbering — research-writer and
    repair-editor are instructed to cite with it directly, so it has to be
    recognized here alongside the reference-list-native S/P/F markers."""
    def sub(m):
        nums: list[str] = []
        last_letter = "S"
        for tok in m.group(1).split(","):
            tok = tok.strip().upper().replace(" ", "")
            if tok and tok[0] in "SPFE":
                last_letter, digits = tok[0], tok[1:]
            else:
                digits = tok
            if not digits.isdigit():
                continue
            n = marker_map.get(f"{last_letter}{digits}")
            if n and str(n) not in nums:
                nums.append(str(n))
        # Inline citation display is disabled by user preference — grounding
        # still shapes the References list; the markers themselves vanish.
        return ""
    out = _CITE.sub(sub, text)
    out = re.sub(r"[ \t]+([.,;:)])", r"\1", out)
    return re.sub(r"(?<=\S) {2,}(?=\S)", " ", out)


def assemble(topic: str, outline: dict, article: dict, images: list[dict],
             evidence: dict, fact_sheet: list[dict] | None = None,
             evidence_claims: list[dict] | None = None) -> dict:
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

    for i, r in enumerate((evidence or {}).get("web", [])[:14]):
        key = (r.get("url") or "").split("#")[0].rstrip("/")
        if not key:
            continue
        n = _add(key, {"title": r.get("title", "")[:200] or key, "url": key,
                       "source": r.get("engine", "web"), "year": None, "doi": ""})
        marker_map[f"S{i+1}"] = n
    for i, p in enumerate((evidence or {}).get("papers", [])[:10]):
        key = (p.get("doi") or p.get("url") or p.get("title", "")).rstrip("/")
        if not key:
            continue
        n = _add(key, {"title": p.get("title", "")[:200], "url": p.get("url", ""),
                       "source": p.get("engine", "academic"), "year": p.get("year"),
                       "doi": p.get("doi", "")})
        marker_map[f"P{i+1}"] = n
    for i, f in enumerate(fact_sheet or []):
        key = (f.get("source_url") or "").split("#")[0].rstrip("/")
        if not key:
            continue
        n = _add(key, {"title": f.get("source_title", "")[:200] or key,
                       "url": key, "source": "official", "year": None, "doi": ""})
        marker_map[f"F{i+1}"] = n
    for e in (evidence_claims or []):
        eid = e.get("id") or ""
        key = (e.get("source_url") or "").split("#")[0].rstrip("/")
        if not eid or not key:
            continue
        # Same dedup key as the web/fact-sheet loops above, so an [E#]
        # claim backed by a URL already seen there reuses that reference
        # entry instead of creating a duplicate.
        n = _add(key, {"title": e.get("source_title", "")[:200] or key,
                       "url": key, "source": "web_search", "year": None, "doi": ""})
        marker_map[eid] = n

    for sec in sections:
        sec["markdown"] = _rewrite_citations(sec["markdown"], marker_map)
        if sec.get("pull_quote"):
            sec["pull_quote"] = re.sub(r"⟦[^⟧]*⟧", "", _rewrite_citations(
                sec["pull_quote"], marker_map)).strip()

    return {
        "topic": topic,
        "title": scrub(article.get("title") or outline.get("title") or topic),
        "layout": outline.get("layout", "research_paper"),
        "abstract": _rewrite_citations(scrub(article.get("abstract", "")), marker_map),
        "key_takeaways": [
            _rewrite_citations(scrub(str(k)), marker_map)
            for k in (article.get("key_takeaways") or [])
            if str(k).strip()][:7],
        "executive_answer": _rewrite_citations(
            scrub(article.get("executive_answer", "")), marker_map),
        "sections": sections,
        "images": images or [],
        "references": references,
    }


def main(argv: list[str]) -> None:
    if len(argv) != 10 or argv[1] != "assemble":
        usage(argv[0] if argv else "final_publisher.py",
             ["assemble <topic.txt> <outline.json> <article.json> <images.json> "
              "<evidence.json> <fact_sheet.json> <evidence_map.json> <out.json>"])
        return
    topic = Path(argv[2]).read_text(encoding="utf-8").strip()
    outline = read_json(argv[3])
    article = read_json(argv[4])
    images = read_json(argv[5])
    evidence = read_json(argv[6])
    fact_sheet = read_json(argv[7])
    evidence_map_raw = read_json(argv[8])
    evidence_claims = (evidence_map_raw.get("evidence", [])
                       if isinstance(evidence_map_raw, dict) else evidence_map_raw) or []
    write_json(argv[9], assemble(topic, outline, article, images, evidence, fact_sheet,
                                 evidence_claims))


if __name__ == "__main__":
    main(sys.argv)
