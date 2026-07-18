"""Universal Abstract Guard — bans template abstracts, enforces specificity."""
from __future__ import annotations

import re

from .llm_gateway import chat_json

BANNED_PATTERNS = [
    r"is a topic whose value depends",
    r"the core anchors (are|for this query)",
    r"develops? .{0,40} from first principles",
    r"is best understood as a structured research problem",
    r"in today'?s (rapidly evolving|fast-paced|ever-changing)",
    r"this article (will )?(explores?|delves? into) the (topic|world) of",
    r"plays a (crucial|vital|pivotal) role in",
]

SYSTEM = """You are the Abstract Quality Agent inside SEARCH AI. Rewrite the
abstract so it reads like the abstract of a strong published piece about THIS
exact topic. It must state, concretely: (1) what the topic is, (2) why it
matters, (3) its mechanism, (4) how it developed from its seminal origins to
its current state, (5) the evidence/metrics involved, (6) risks or
limitations, (7) what the article establishes and what remains open. 150-220 words. Every sentence
must be unusable for any other topic. No meta-language about "this query",
"anchors", "first principles", or "structured research problems".
Return JSON: {"abstract": "..."}"""


def is_generic(abstract: str) -> list[str]:
    hits = []
    low = abstract.lower()
    for pat in BANNED_PATTERNS:
        if re.search(pat, low):
            hits.append(pat)
    if len(abstract.split()) < 60:
        hits.append("too_short")
    return hits


async def run(article: dict, topic: str, domain: str) -> tuple[dict, bool]:
    abstract = article.get("abstract", "")
    problems = is_generic(abstract)
    if not problems:
        return article, False
    body_hint = "\n".join(f"- {s['title']}: {s['markdown'][:220]}"
                          for s in article.get("sections", [])[:6])
    user = (f"Topic: {topic}\nDomain: {domain}\n\nCurrent abstract "
            f"(rejected for: {problems}):\n{abstract}\n\n"
            f"Article section hints:\n{body_hint}")
    try:
        out = await chat_json("editor", SYSTEM, user,
                              max_tokens=700, temperature=0.5)
        new_abs = out.get("abstract", "").strip()
        if new_abs and not is_generic(new_abs):
            article["abstract"] = new_abs
            return article, True
        if new_abs:
            article["abstract"] = new_abs
            return article, True
    except Exception:
        pass
    return article, False
