"""Outline Approval Agent — generates the editable, topic-adaptive outline
that jointly satisfies the answer contract and carries the temporal arc."""
from __future__ import annotations

import json
import re

from ..services.llm_gateway import chat_json

LAYOUTS = ["research_paper", "strategic_briefing", "decision_memo",
           "technical_field_guide", "mathematical_explainer",
           "security_operations_report", "implementation_playbook",
           "comparative_analysis", "historical_timeline",
           "current_intelligence_briefing"]

SYSTEM = f"""You are the Outline Approval Agent inside SEARCH AI. Design the
outline the article will be contractually bound to. Rules:

QUERY LOCK — the outline exists only to answer the searched query:
- Every section must visibly serve the query lock. A reader scanning only
  the section titles should already see the query being answered.
- Section titles must name concrete entities/mechanisms of THIS topic
  (e.g. "How the Bias-Variance Tradeoff Produces Overfitting", never
  "Background" alone). No section may match an adjacent-topic to avoid.
- The sections must JOINTLY cover every item of the answer contract; when
  you place a contract item, reflect it in that section's subpoints.

ADAPTIVE STRUCTURE:
- Choose the best layout from: {", ".join(LAYOUTS)}. Never reuse one fixed
  template. 6-10 top-level sections, each with a one-line goal and 2-5
  subpoints naming the concrete content it will deliver.
- Include, adapted to the layout: a direct answer/executive element early,
  mechanism/core content, evidence or worked examples, risks/limitations,
  and a final judgement or verdict element. No references section (handled
  outside the outline).

TEMPORAL ARC — doctoral articles own their timeline. Unless the layout makes
it absurd, the outline must carry, woven into topic-specific sections (not
bolted on as generic "History"/"Future" filler):
- historical grounding: where this topic came from — seminal work, original
  formulation, key milestones;
- the current frontier: the {'{'}state-of-the-art / present status{'}'} of
  the topic;
- the forward horizon: open problems, active research directions, credible
  trajectory — as a subpoint or section near the end.
For latest/current topics choose current_intelligence_briefing or
strategic_briefing and include a verified-current-facts section; the arc
then runs recent-past -> now -> next.

REGISTER — if the intent is how / implementation (or the layout is a
playbook or field guide), design a BUILDER'S GUIDE: verb-first,
step-oriented section titles that walk from setup to working result
(project setup -> core workflow steps -> validation -> automation ->
common mistakes -> operating principle). For each such section, one
subpoint must name the concrete artifact that section will deliver
(a prompt, config file, directory tree, schema, table or checklist).
Explanatory/research topics keep analytical section titles.

NARRATIVE THREAD — the article must read as ONE argument, not stacked
essays. Provide:
- "narrative_thread": one sentence stating the through-line that every
  section advances, from opening to verdict.
- per section, "bridge_from_previous": the logical link this section picks
  up from the one before it (empty for the first section) — a handoff the
  writer will turn into an organic transition, and
- "key_questions": 2-3 sharp questions THIS section must answer for the
  thread to advance.
Return JSON:
{{"layout": "...", "title": "strong specific article title",
  "narrative_thread": "...",
  "sections": [{{"title": "...", "goal": "...", "subpoints": ["..."],
                "bridge_from_previous": "...", "key_questions": ["..."]}}]}}"""


def _slug(text: str, i: int) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48]
    return f"s{i+1}-{base or 'section'}"


def _extract_sections(raw: dict) -> list:
    """JSON-mode models sometimes nest or rename the sections array."""
    v = raw.get("sections")
    if isinstance(v, list) and v:
        return v
    inner = raw.get("outline")
    if isinstance(inner, dict):
        raw.setdefault("title", inner.get("title"))
        raw.setdefault("layout", inner.get("layout"))
        v = inner.get("sections")
        if isinstance(v, list) and v:
            return v
    for _, v in raw.items():
        if (isinstance(v, list) and v and isinstance(v[0], dict)
                and "title" in v[0]):
            return v
    return []


async def run(topic: str, analysis: dict, brief: dict, options: dict) -> dict:
    forced = options.get("format", "auto")
    extra = ""
    if forced != "auto":
        extra = f"\nThe user forced layout = {forced}. Use exactly that layout."
    depth = options.get("depth", "deep")
    user = (f"Topic: {topic}\nDepth: {depth}\n"
            f"Query lock: {analysis.get('query_lock','')}\n"
            f"Do NOT drift into: {analysis.get('adjacent_topics_to_avoid', [])}\n"
            f"Answer contract the sections must jointly satisfy:\n"
            f"{json.dumps(brief.get('answer_contract', []), ensure_ascii=False)}\n\n"
            f"Analysis:\n{json.dumps(analysis, ensure_ascii=False)[:2000]}\n\n"
            f"Research brief:\n{json.dumps(brief, ensure_ascii=False)[:2400]}"
            f"{extra}")
    raw: dict = {}
    raw_sections: list = []
    for attempt in range(2):
        prompt = user if attempt == 0 else (
            user + "\n\nYOUR PREVIOUS ATTEMPT RETURNED NO SECTIONS. You "
            "MUST return a non-empty \"sections\" array of 6-10 objects, "
            "each with title, goal and subpoints. Return the full JSON now.")
        raw = await chat_json("writer", SYSTEM, prompt,
                              max_tokens=4200,
                              temperature=0.5 if attempt == 0 else 0.65)
        raw_sections = _extract_sections(raw)
        if len(raw_sections) >= 3:
            break
    if len(raw_sections) < 3:
        from ..services.llm_gateway import LLMError
        raise LLMError("The outline model returned no usable sections after "
                       "two attempts — press 'Regenerate outline' to retry, "
                       "or check the model names in .env.")
    sections = []
    for i, sec in enumerate(raw_sections[:12]):
        if isinstance(sec, str):
            sec = {"title": sec}
        subs = sec.get("subpoints", [])
        if isinstance(subs, str):
            subs = [subs]
        kq = sec.get("key_questions", [])
        if isinstance(kq, str):
            kq = [kq]
        sections.append({
            "id": _slug(str(sec.get("title", f"section {i+1}")), i),
            "title": str(sec.get("title", f"Section {i+1}")).strip(),
            "goal": str(sec.get("goal", "") or "").strip(),
            "subpoints": [str(p).strip() for p in subs if str(p).strip()][:6],
            "bridge": str(sec.get("bridge_from_previous", "") or "").strip(),
            "key_questions": [str(q).strip() for q in kq
                              if str(q).strip()][:3],
        })
    layout = raw.get("layout", "research_paper")
    if forced != "auto":
        layout = forced
    return {"layout": layout,
            "title": raw.get("title", topic).strip(),
            "narrative_thread": str(raw.get("narrative_thread", "")
                                    or "").strip(),
            "sections": sections}
