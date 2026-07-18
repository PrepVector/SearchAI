"""Currentness engine — verified current facts BEFORE writing, and a
section-level output guard AFTER writing.

Two duties:
1. prefetch_current_facts(): for time-sensitive topics, retrieve fresh
   official-leaning evidence up front and distil it into a VERIFIED CURRENT
   FACTS sheet the writer must obey — so stale training memory never gets
   drafted in the first place.
2. run(): audit the finished article against the same fresh evidence.
   Sentence-level corrections for isolated slips; WHOLE-SECTION rewrites
   when a section (e.g. a model registry table) is pervasively stale.
"""
from __future__ import annotations

import json
from datetime import date

from . import search_gateway
from .llm_gateway import chat_json

FACTS_SYSTEM = """You are the Current Facts Extractor inside SEARCH AI.
Today's date is {today}. From ONLY the fresh evidence supplied (never your
memory), extract the verified current facts that matter for the topic:
names, versions, releases, identifiers, dates, prices, figures, rankings,
statuses. Rules:
- Only facts a supplied snippet explicitly states. No inference beyond it.
- Each fact is one self-contained sentence with its concrete value.
- as_of = the date/period the evidence gives, else "retrieved {today}".
- Prefer official/vendor/primary sources when snippets conflict; if a
  conflict is unresolvable, state both values as a single fact noting the
  conflict.
Return JSON:
{{"facts": [{{"fact": "...", "as_of": "...", "source_i": n}}],
  "note": "one sentence on how current/complete the evidence is"}}
5-14 facts. source_i is the index of the supporting evidence item."""

GUARD_SYSTEM = """You are the Currentness Output Guard inside SEARCH AI.
Today's date is {today}. The topic is time-sensitive. Audit the article's
current-fact claims (model names, versions, prices, laws, rankings, product
data, dates) against ONLY the fresh evidence supplied — never your memory.

Decide per section:
- ISOLATED slip -> sentence correction: replacement either states the
  verified current value citing the evidence, or states plainly that the
  exact current value must be checked from official docs/API.
- PERVASIVELY STALE section (e.g. an outdated registry, version table,
  ranking, or narrative built on superseded facts) -> rewrite the WHOLE
  section: same purpose, same approximate length, same markdown style
  (keep tables as tables), grounded ONLY in the fresh evidence, with
  explicit as-of dating. Keep any [S#]/[P#]/[F#] markers that remain valid.
Never leave a superseded name/version/date presented as current anywhere,
including inside tables and code comments.
At most 2 section_rewrites — pick the most stale-dense sections; use
sentence corrections everywhere else. Return JSON:
{{"status": "current" | "corrected" | "unverified",
 "corrections": [{{"section_id":"...", "old":"exact old sentence",
                  "new":"replacement sentence"}}],
 "section_rewrites": [{{"section_id":"...", "markdown":"full new body"}}],
 "note": "one sentence status"}}"""


def _official_rank(results: list[dict], official: list[str]) -> list[dict]:
    off = [d.lower() for d in official]

    def score(r: dict) -> float:
        s = float(r.get("score") or 0)
        url = (r.get("url") or "").lower()
        if any(d in url for d in off):
            s += 6.0
        if any(t in url for t in (".gov", "docs.", "developer.", ".edu",
                                  "official", "release")):
            s += 2.0
        return s

    return sorted(results, key=score, reverse=True)


async def prefetch_current_facts(topic: str, plan: dict,
                                 analysis: dict) -> tuple[list[dict], list[dict]]:
    """Return (fact_sheet, fresh_evidence). Empty lists if nothing found."""
    year = date.today().year
    queries = [f"{topic} official documentation {year}",
               f"{topic} latest {year}"]
    queries += list(plan.get("extra_official_queries", []))[:3]
    for ent in list(analysis.get("key_entities", []))[:2]:
        queries.append(f"{ent} official docs {year}")
    fresh = await search_gateway.web_search(queries[:7], per_query=4,
                                            recent=True)
    fresh = _official_rank(fresh, plan.get("official_domains", []))[:12]
    for r in fresh:
        r["engine"] = "official"
    if not fresh:
        return [], []

    ev = [{"i": i, "title": r.get("title", "")[:110],
           "url": r.get("url", "")[:130],
           "published": r.get("published", ""),
           "snippet": r.get("snippet", "")[:420]} for i, r in enumerate(fresh)]
    today = date.today().isoformat()
    try:
        out = await chat_json(
            "validator", FACTS_SYSTEM.format(today=today),
            f"Topic: {topic}\n\nFRESH EVIDENCE:\n"
            f"{json.dumps(ev, ensure_ascii=False)}",
            max_tokens=2200, temperature=0.1)
    except Exception:
        return [], fresh

    facts = []
    for f in (out.get("facts", []) or [])[:14]:
        try:
            i = int(f.get("source_i"))
        except (TypeError, ValueError):
            i = -1
        src = fresh[i] if 0 <= i < len(fresh) else {}
        facts.append({"fact": str(f.get("fact", ""))[:400],
                      "as_of": str(f.get("as_of", today))[:60],
                      "source_title": src.get("title", "")[:110],
                      "source_url": src.get("url", "")[:150]})
    return [f for f in facts if f["fact"]], fresh


async def run(article: dict, topic: str, plan: dict, time_sensitive: bool,
              fresh: list[dict] | None = None) -> tuple[dict, dict]:
    if not time_sensitive or not plan.get("verify_currentness", False):
        return article, {"status": "not_required",
                         "note": "Topic is not time-sensitive."}

    if fresh is None:
        year = date.today().year
        queries = [f"{topic} official documentation {year}",
                   f"{topic} latest {year}"]
        queries += plan.get("extra_official_queries", [])[:2]
        fresh = await search_gateway.web_search(queries, per_query=4,
                                                recent=True)
    if not fresh:
        return article, {"status": "unverified",
                         "note": "No fresh sources reachable — time-sensitive "
                                 "values should be confirmed from official docs."}

    ev = [{"title": r.get("title", "")[:110], "url": r.get("url", "")[:130],
           "published": r.get("published", ""),
           "snippet": r.get("snippet", "")[:400]} for r in fresh[:12]]
    body = "\n\n".join(f"## {s['title']} (id={s['id']})\n{s['markdown'][:1700]}"
                       for s in article.get("sections", []))
    user = (f"Topic: {topic}\n\nFRESH EVIDENCE:\n"
            f"{json.dumps(ev, ensure_ascii=False)}\n\nARTICLE:\n{body[:18000]}")
    try:
        verdict = await chat_json(
            "validator", GUARD_SYSTEM.format(today=date.today().isoformat()),
            user, max_tokens=3600, temperature=0.1)
    except Exception:
        return article, {"status": "unverified",
                         "note": "Currentness check unavailable; time-sensitive "
                                 "values should be confirmed from official docs."}

    by_id = {s.get("id"): s for s in article.get("sections", [])}
    rewritten = 0
    for rw in verdict.get("section_rewrites", []) or []:
        sec = by_id.get(rw.get("section_id"))
        md = (rw.get("markdown") or "").strip()
        if sec and len(md) > 80:
            sec["markdown"] = md
            rewritten += 1
    for corr in verdict.get("corrections", []) or []:
        old, new = corr.get("old", ""), corr.get("new", "")
        if len(old) < 12 or not new:
            continue
        for sec in article.get("sections", []):
            if old in sec.get("markdown", ""):
                sec["markdown"] = sec["markdown"].replace(old, new, 1)
                break
    if rewritten:
        verdict["note"] = (verdict.get("note", "") +
                           f" ({rewritten} section(s) rewritten to current facts)").strip()
        verdict["status"] = verdict.get("status") or "corrected"
    return article, verdict
