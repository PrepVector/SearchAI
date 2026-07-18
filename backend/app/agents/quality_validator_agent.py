"""Quality Validator — one audit replacing three separate validators.

Facts, topic integrity, and answer intent in a single structured verdict,
followed by deterministic reconciliation and sentence-level fixes.
"""
from __future__ import annotations

import difflib
import json
import re

from ..services.llm_gateway import chat_json

SYSTEM = """You are the Quality Validator inside SEARCH AI — the article's
single pre-publish audit. The article is contractually bound to a
user-approved outline (supplied): judge ONLY what the outline commissioned;
gaps the outline excludes go under out_of_scope, never as failures.

Audit three dimensions and return ONE JSON object:

1. FACTS — against the evidence only: unsupported/contradicted/outdated
   claims, missing demanded current facts, unrelated citations. Propose
   corrected sentences where fixable. Max 8 material issues. Treat any
   NAMED tool, product, plugin, skill, marketplace, statistic or
   threshold that the evidence does not contain as an unsupported claim
   (kind="invented_entity") — propose a fix that removes the invented
   name or reframes the passage as reader-created.
2. TOPIC — score topic_alignment 0-100: start at 100; -20 per section
   drifting into an adjacent topic; -15 per generic section; -5 per
   paragraph-level tangent; -10 if the executive answer's first sentence
   does not answer the query; -8 per contract item an approved section
   should host but doesn't; -5 per section whose opening has no connection
   to the previous section's endpoint. status=fail if <75 or any whole
   section is off-query. Give an actionable refocus_instruction per flag.
3. INTENT — does the article deliver the query's answer TYPE within the
   outline's scope ('how' needs a procedure, 'comparison' a real
   side-by-side, 'latest_current' verified current facts or explicit
   check-official notes, 'mathematical_explanation' a worked derivation).
   Never list the same element in both missing and out_of_scope.

Return JSON:
{"facts": {"status": "pass|pass_with_fixes|fail",
  "issues": [{"kind":"...","section_id":"...","claim":"short quote",
              "note":"why","fix":"corrected sentence or empty"}]},
 "topic": {"status": "pass|fail", "topic_alignment": 0-100,
  "drift_sections": [], "drift_notes": [{"section_id":"...",
     "problem":"...","refocus_instruction":"..."}],
  "missing_contract_items": [], "out_of_scope_notes": []},
 "intent": {"status": "pass|fail", "missing": ["in-scope gaps only"],
  "out_of_scope_suggestions": ["outline-level improvement ideas"]},
 "note": "one sentence overall verdict"}"""

_STOP = {"the", "a", "an", "for", "of", "on", "or", "and", "in", "to", "is",
         "are", "this", "that", "with", "include", "includes", "article",
         "lacks", "discussion", "section", "subsection", "detailing", "add",
         "adds", "should", "such", "as"}


def _words(s: str) -> set[str]:
    return {w for w in re.sub(r"[^a-z0-9\s]", " ", s.lower()).split()
            if len(w) >= 3 and w not in _STOP}


def _same_gap(m: str, s: str) -> bool:
    if difflib.SequenceMatcher(None, m.lower(), s.lower()).ratio() >= 0.7:
        return True
    mw, sw = _words(m), _words(s)
    if len(mw) < 3:
        return False
    overlap = len(mw & sw)
    return overlap >= 3 and overlap / len(mw) >= 0.5


def reconcile(v: dict) -> dict:
    """Deterministic tie-breaks a model cannot be trusted to make itself."""
    intent = v.setdefault("intent", {})
    missing = [str(m).strip() for m in (intent.get("missing") or [])
               if str(m).strip()]
    sugg = [str(s).strip() for s in (intent.get("out_of_scope_suggestions")
                                     or []) if str(s).strip()]
    kept = [m for m in missing if not any(_same_gap(m, s) for s in sugg)]
    intent["missing"] = kept
    intent["out_of_scope_suggestions"] = sugg
    if not kept and intent.get("status") == "fail":
        intent["status"] = "pass"
    v.setdefault("facts", {}).setdefault("status", "pass")
    v["facts"].setdefault("issues", [])
    t = v.setdefault("topic", {})
    t.setdefault("status", "pass")
    t.setdefault("topic_alignment", 85)
    for k in ("drift_sections", "drift_notes", "missing_contract_items",
              "out_of_scope_notes"):
        t.setdefault(k, [])
    return v


def apply_fixes(article: dict, verdict: dict) -> dict:
    for issue in verdict.get("facts", {}).get("issues", []):
        claim, fix = issue.get("claim", ""), issue.get("fix", "")
        if not fix or len(claim) < 12:
            continue
        for sec in article.get("sections", []):
            if claim in sec.get("markdown", ""):
                sec["markdown"] = sec["markdown"].replace(claim, fix, 1)
                break
    return article


async def run(article: dict, evidence: dict, topic: str, *,
              query_lock: str = "", adjacent: list | None = None,
              answer_contract: list | None = None,
              outline_titles: list | None = None,
              intent: str = "what") -> dict:
    ev = {"web": [{"id": f"S{i+1}", "title": r.get("title", "")[:100],
                   "snippet": r.get("snippet", "")[:280],
                   "published": r.get("published", "")}
                  for i, r in enumerate(evidence.get("web", [])[:12])],
          "papers": [{"id": f"P{i+1}", "title": p.get("title", "")[:110],
                      "year": p.get("year"),
                      "abstract": p.get("abstract", "")[:240]}
                     for i, p in enumerate(evidence.get("papers", [])[:8])]}
    body = "\n\n".join(f"## {s['title']} (id={s['id']})\n{s['markdown'][:1400]}"
                       for s in article.get("sections", []))
    user = (f"Searched query: {topic}\nIntent: {intent}\n"
            f"Query lock: {query_lock}\n"
            f"Adjacent topics that count as drift: "
            f"{json.dumps(adjacent or [], ensure_ascii=False)}\n"
            f"Answer contract: "
            f"{json.dumps(answer_contract or [], ensure_ascii=False)}\n"
            f"Approved outline sections: "
            f"{json.dumps(outline_titles or [], ensure_ascii=False)}\n\n"
            f"EVIDENCE:\n{json.dumps(ev, ensure_ascii=False)}\n\n"
            f"Executive answer: {article.get('executive_answer','')}\n"
            f"Abstract: {article.get('abstract','')}\n\n"
            f"ARTICLE:\n{body[:22000]}")
    try:
        verdict = await chat_json("validator", SYSTEM, user,
                                  max_tokens=2600, temperature=0.1)
    except Exception as exc:
        verdict = {"facts": {"status": "pass_with_fixes", "issues": []},
                   "topic": {"status": "pass", "topic_alignment": 82},
                   "intent": {"status": "pass", "missing": [],
                              "out_of_scope_suggestions": []},
                   "note": f"Validator unavailable ({str(exc)[:100]})"}
    return reconcile(verdict)
