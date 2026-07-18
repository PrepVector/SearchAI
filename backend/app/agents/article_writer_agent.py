"""Article Writer — markdown-native, thinking-enabled, chunked for depth.

The writer produces PURE MARKDOWN with lightweight block delimiters instead
of JSON. Frontier models write markedly better prose outside JSON string
escaping, and extended thinking (enabled at the gateway for writer calls)
lets them plan before drafting — the two changes that close the gap to
chat-app output quality.
"""
from __future__ import annotations

import json
import re
from datetime import date

from ..services.llm_gateway import LLMError, chat

SYSTEM = """You are the Article Writer inside SEARCH AI, writing a premium
research article at the level of the best professional analysts. Today's
year is {year}. HARD RULES, in priority order:

1. QUERY LOCK — the searched query is the thesis:
- Every paragraph must advance the answer to the exact query. The listed
  adjacent topics are PROHIBITED except as one-line contrasts.
- The ANSWER block must answer the query directly in its FIRST sentence.
- Every answer-contract item must be explicitly delivered in the section
  the outline assigned it to.

2. OUTLINE CONTRACT — write EXACTLY the sections listed for this pass, same
order. Anything extra goes INSIDE the most relevant section.

3. DEPTH LADDER — every major claim descends at least three rungs: claim ->
mechanism (why it holds) -> quantification or named concrete example ->
implication or limit. Assertion-only paragraphs are defects. Mine the
evidence hard: each section draws on 2+ distinct evidence items where the
evidence allows.

4. FLOW — one argument on the narrative thread: every section after the
first OPENS by advancing from the previous section's endpoint via its
bridge (organically — never "as discussed above"); answer each section's
key questions inside it; one term per concept throughout.

5. REGISTER — match the document type the query actually asks for:
- HOW-TO / IMPLEMENTATION / PLAYBOOK / GUIDE intents (and layouts like
  implementation_playbook or technical_field_guide): write a practical
  builder's guide, not a paper ABOUT the idea. Verb-first step headings;
  direct address ("create", "ask", "run") is correct here. EVERY major
  step must hand the reader a usable artifact in a fenced code block:
  a copy-pasteable prompt, a config file, a directory tree, a command,
  a schema, or a checklist. Thread ONE realistic worked example through
  the whole article (same product/scenario in every section). Include a
  "common mistakes" treatment where the outline allows. Prefer tables
  for any mapping (criteria/weights, metric/owner, option/trade-off).
- RESEARCH / EXPLANATORY / COMPARISON intents: scholarly analyst
  register as below.

6. TRUTH BOUNDARY — never present a tool, product, plugin, skill,
company, marketplace, statistic, threshold, benchmark or version as REAL
unless the evidence contains it from an authoritative source. Anything
illustrative must be unmistakably framed as something the READER creates
or chooses ("a scoring model you might adopt", "for example, you could
weight customer value at 25%") — never given an invented proper-noun
name, a (TM), or a fake citation. Inventing a named product or a numeric
"finding" is the worst possible failure after a stale fact.

7. PROSE — write like a senior scholar for peers: varied rhythm, confident
precision, zero filler or template language. LaTeX math ($..$, $$..$$),
markdown tables with bold headers for comparisons/specs, ### sub-headings
inside long sections, **bold** for key terms, pivotal numbers and verdicts.
Fenced code only where genuinely useful for the topic. Never ASCII box-art,
never raw HTML, never your own references section.

8. TEMPORAL ARC — weave through the given sections: seminal origins (named
researchers/years from [P#]), the verified current state ([S#]/[F#] —
the VERIFIED CURRENT FACTS override your memory; a superseded value
presented as current is the worst possible failure; unverified current
values must say "confirm from official documentation"), and future
trajectory framed transparently as outlook.

9. EVIDENCE — mark support like [S3]/[P2]/[F1] after the sentences the
cited item genuinely supports.

10. LENGTH — 350-600 words per section; substance decides within that.

OUTPUT FORMAT — plain text with these exact delimiters, NO JSON, no code
fences around the whole output:

=== TITLE ===
one strong specific title
=== ABSTRACT ===
150-220 word publication-grade abstract for THIS topic (what it is, why it
matters, mechanism, how it developed to the present, evidence, limits, what
the article establishes — no sentence reusable for another topic)
=== ANSWER ===
80-160 word direct answer
=== TAKEAWAYS ===
- 5-7 one-sentence insights, each SYNTHESIZING across 2+ sections
=== SECTION: <id> | <exact section title> ===
PULL QUOTE: at most one striking information-dense sentence (only in 2-4
sections total across the article, never the first; omit this line elsewhere)
full markdown body of the section
(repeat the SECTION block for every section of this pass, in order)"""


# ---------------------------------------------------------------- parsing
_BLOCK = re.compile(
    r"^===\s*(TITLE|ABSTRACT|ANSWER|TAKEAWAYS|SECTION)"
    r"(?:\s*:\s*([^\n=]+?))?\s*===\s*$", re.MULTILINE)


def parse_article_md(text: str) -> dict:
    """Parse the delimited-markdown article format back into the article
    dict every downstream component expects."""
    text = text.replace("\r\n", "\n").strip()
    text = re.sub(r"^```[a-z]*\n|```$", "", text).strip()
    out = {"title": "", "abstract": "", "executive_answer": "",
           "key_takeaways": [], "sections": []}
    matches = list(_BLOCK.finditer(text))
    for i, m in enumerate(matches):
        kind = m.group(1).upper()
        param = (m.group(2) or "").strip()
        body = text[m.end():matches[i + 1].start() if i + 1 < len(matches)
                    else len(text)].strip()
        if kind == "TITLE":
            out["title"] = body.splitlines()[0].strip() if body else ""
        elif kind == "ABSTRACT":
            out["abstract"] = body
        elif kind == "ANSWER":
            out["executive_answer"] = body
        elif kind == "TAKEAWAYS":
            out["key_takeaways"] = [
                re.sub(r"^[-•*]\s*", "", ln).strip()
                for ln in body.splitlines()
                if re.match(r"^\s*[-•*]", ln)][:7]
        elif kind == "SECTION":
            sid, _, stitle = param.partition("|")
            pull = None
            lines = body.splitlines()
            for j, ln in enumerate(lines):
                if not ln.strip():
                    continue
                if ln.strip().upper().startswith("PULL QUOTE:"):
                    pull = ln.split(":", 1)[1].strip()
                    lines = lines[:j] + lines[j + 1:]
                break
            out["sections"].append({
                "id": sid.strip(), "title": stitle.strip(),
                "markdown": "\n".join(lines).strip(),
                "pull_quote": pull})
    return out


def serialize_article_md(article: dict) -> str:
    parts = [f"=== TITLE ===\n{article.get('title','')}",
             f"=== ABSTRACT ===\n{article.get('abstract','')}",
             f"=== ANSWER ===\n{article.get('executive_answer','')}",
             "=== TAKEAWAYS ===\n" +
             "\n".join(f"- {k}" for k in article.get("key_takeaways", []))]
    for s in article.get("sections", []):
        head = f"=== SECTION: {s.get('id','')} | {s.get('title','')} ==="
        pq = (f"PULL QUOTE: {s['pull_quote']}\n"
              if s.get("pull_quote") else "")
        parts.append(f"{head}\n{pq}{s.get('markdown','')}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------- writing
def _evidence_block(web: list[dict], papers: list[dict]) -> str:
    lines = []
    for i, r in enumerate(web[:12]):
        lines.append(f"[S{i+1}] {r.get('title','')[:110]} | {r.get('url','')[:120]} "
                     f"| {r.get('published','')} | {r.get('snippet','')[:420]}")
    for i, p in enumerate(papers[:8]):
        lines.append(f"[P{i+1}] {p.get('title','')[:120]} ({p.get('year','?')}) "
                     f"DOI:{p.get('doi','')} cited:{p.get('cited_by',0)} | "
                     f"{p.get('abstract','')[:380]}")
    return "\n".join(lines) or "(no external evidence retrieved — rely on "\
        "established knowledge and flag anything time-sensitive as needing "\
        "official confirmation)"


def _facts_block(fact_sheet: list[dict] | None) -> str:
    if not fact_sheet:
        return ("(none retrieved — treat every 'current' value as "
                "unconfirmed and say so explicitly)")
    return "\n".join(
        f"[F{i+1}] {f.get('fact','')} — as of {f.get('as_of','')} — "
        f"{f.get('source_title','')} ({f.get('source_url','')})"
        for i, f in enumerate(fact_sheet))


def _continuity_block(done: list[dict]) -> str:
    if not done:
        return ""
    lines = ["CONTINUITY — sections already written (do NOT rewrite them):"]
    for s in done:
        first = (s.get("markdown", "").strip().split("\n") or [""])[0][:180]
        lines.append(f"- {s.get('title','')}: {first}")
    tail = done[-1].get("markdown", "").strip()[-700:]
    lines.append("VERBATIM ENDING of the last written section — your first "
                 "new section must advance organically from this exact "
                 "endpoint:\n" + tail)
    return "\n".join(lines)


async def _write_pass(topic, analysis, brief, outline, evidence, fact_sheet,
                      target_sections, done, final) -> dict:
    scope = ("Write ONLY these sections now, each as its own "
             "=== SECTION: id | title === block:\n" +
             "\n".join(f"- {s['id']} | {s['title']}"
                       for s in target_sections))
    if final and done:
        scope += ("\nTAKEAWAYS must span the ENTIRE article — the "
                  "already-written sections and yours.")
    elif not final:
        scope += "\nLeave the TAKEAWAYS block empty in this pass."
    pass_outline = {**outline, "sections": target_sections}
    user = (
        f"Searched query: {topic}\n"
        f"QUERY LOCK: {analysis.get('query_lock','')}\n"
        f"PROHIBITED adjacent topics: "
        f"{json.dumps(analysis.get('adjacent_topics_to_avoid', []), ensure_ascii=False)}\n"
        f"ANSWER CONTRACT:\n"
        f"{json.dumps(brief.get('answer_contract', []), ensure_ascii=False)}\n"
        f"Intent: {analysis.get('intent')} · Audience: {analysis.get('audience')}"
        f" · Layout: {outline.get('layout')}\n"
        f"NARRATIVE THREAD: {outline.get('narrative_thread','')}\n"
        f"{scope}\n"
        f"{_continuity_block(done)}\n\n"
        f"APPROVED OUTLINE for THIS pass (contract):\n"
        f"{json.dumps(pass_outline, ensure_ascii=False, indent=1)}\n\n"
        f"RESEARCH QUESTIONS:\n"
        f"{json.dumps(brief.get('research_questions', []), ensure_ascii=False)}\n\n"
        f"VERIFIED CURRENT FACTS (override memory, cite as [F#]):\n"
        f"{_facts_block(fact_sheet)}\n\n"
        f"EVIDENCE:\n{_evidence_block(evidence.get('web', []), evidence.get('papers', []))}\n\n"
        "Write this pass now in the exact delimited format."
    )
    sysmsg = SYSTEM.format(year=date.today().year)
    for attempt in range(2):
        raw = await chat("writer", sysmsg, user, max_tokens=9000,
                         temperature=0.7, thinking=True)
        parsed = parse_article_md(raw)
        if parsed["sections"]:
            return parsed
        user += ("\n\nYOUR PREVIOUS OUTPUT CONTAINED NO SECTION BLOCKS. "
                 "Follow the delimiter format exactly.")
    raise LLMError("Writer produced no sections in the delimited format "
                   "after two attempts.")


async def run(topic: str, analysis: dict, brief: dict, outline: dict,
              evidence: dict, options: dict,
              fact_sheet: list[dict] | None = None) -> dict:
    """Chunked two-pass writing for long outlines so the output ceiling
    never truncates substance; single pass for short ones."""
    secs = outline.get("sections", [])
    if len(secs) <= 5:
        return await _write_pass(topic, analysis, brief, outline, evidence,
                                 fact_sheet, secs, [], final=True)
    k = (len(secs) + 1) // 2
    first = await _write_pass(topic, analysis, brief, outline, evidence,
                              fact_sheet, secs[:k], [], final=False)
    done = first.get("sections", [])
    second = await _write_pass(topic, analysis, brief, outline, evidence,
                               fact_sheet, secs[k:], done, final=True)
    return {
        "title": first.get("title") or second.get("title") or topic,
        "abstract": first.get("abstract", ""),
        "executive_answer": first.get("executive_answer", ""),
        "key_takeaways": second.get("key_takeaways")
                         or first.get("key_takeaways") or [],
        "sections": done + second.get("sections", []),
    }
