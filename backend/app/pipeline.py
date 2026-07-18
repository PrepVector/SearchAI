"""SEARCH AI pipeline v2 — consolidated agents, parallel lanes.

Phase 1 (outline):   Research Director -> Outline Architect (editable)
Phase 2 (generate):  retrieval -> credibility -> [facts ∥ visual hunt] ->
                     markdown writer (thinking) -> contract -> polish ->
                     [currentness ∥ image embed] -> quality validator ->
                     repair (conditional) -> contract -> gate -> formatter
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Callable

from .agents import (academic_research_agent, article_writer_agent,
                     final_formatter_agent, image_regeneration_agent,
                     outline_approval_agent, quality_validator_agent,
                     research_director_agent, source_credibility_agent,
                     text_enhancer_agent, visual_reference_agent,
                     web_research_agent)
from .agents.text_enhancer_agent import FIELD_STANDARDS
from .config import get_settings
from .services import (currentness_output_guard, outline_contract_engine,
                       universal_abstract_guard)


class Trace:
    def __init__(self) -> None:
        self.steps: list[dict[str, Any]] = []

    async def run(self, name: str, coro, note_fn: Callable[[Any], str] | None = None):
        t0 = time.perf_counter()
        try:
            result = await coro
        except Exception as exc:
            self.steps.append({"agent": name, "status": "error",
                               "ms": int((time.perf_counter() - t0) * 1000),
                               "note": str(exc)[:220]})
            raise
        note = ""
        if note_fn:
            try:
                note = note_fn(result)
            except Exception:
                note = "(result summary unavailable)"
        self.steps.append({"agent": name, "status": "ok",
                           "ms": int((time.perf_counter() - t0) * 1000),
                           "note": note})
        return result

    def soft(self, name: str, status: str, note: str = ""):
        self.steps.append({"agent": name, "status": status, "ms": 0,
                           "note": note[:260]})


def _safe(res, default):
    return default if isinstance(res, BaseException) else res


# ------------------------------------------------------------- phase 1
async def build_outline(topic: str, options: dict) -> dict:
    trace = Trace()
    d = await trace.run(
        "Research Director",
        research_director_agent.run(topic, options),
        lambda r: f"domain={r['analysis'].get('domain')} · "
                  f"intent={r['analysis'].get('intent')} · "
                  f"time_sensitive={r['analysis'].get('is_time_sensitive')}")
    analysis, brief, plan = d["analysis"], d["brief"], d["plan"]
    outline = await trace.run(
        "Outline Architect",
        outline_approval_agent.run(topic, analysis, brief, options),
        lambda o: f"layout={o.get('layout')} · "
                  f"{len(o.get('sections', []))} sections · narrative thread set")
    analysis["_brief"] = brief
    analysis["_plan"] = plan
    return {"topic": topic, "analysis": analysis,
            "outline": outline, "trace": trace.steps}


# ------------------------------------------------------------- phase 2
async def generate_article(topic: str, outline: dict, analysis: dict | None,
                           options: dict) -> dict:
    s = get_settings()
    trace = Trace()
    t0 = time.perf_counter()
    warnings: list[str] = []

    # ---- one director call covers understanding + brief + plan
    brief = (analysis or {}).get("_brief") or {}
    plan = (analysis or {}).get("_plan") or {}
    if not analysis or "query_lock" not in analysis or not brief or not plan:
        d = await trace.run(
            "Research Director",
            research_director_agent.run(topic, options),
            lambda r: f"domain={r['analysis'].get('domain')} · "
                      f"intent={r['analysis'].get('intent')}")
        analysis, brief, plan = d["analysis"], d["brief"], d["plan"]
    else:
        trace.soft("Research Director", "reused",
                   f"domain={analysis.get('domain')} · brief and plan "
                   "carried over from the outline phase")
    # user toggles are law, even on reused plans
    if not options.get("web_research", True):
        plan["use_web_search"] = False
    if not options.get("current_findings", True):
        plan["verify_currentness"] = False
    time_sensitive = bool(analysis.get("is_time_sensitive")) and \
        options.get("current_findings", True)

    # ---- retrieval (web + academic in parallel)
    web_raw, papers_raw = await asyncio.gather(
        web_research_agent.run(brief, plan, time_sensitive),
        academic_research_agent.run(brief, plan))
    trace.soft("Web Research", "ok" if web_raw else
               ("skipped" if not plan.get("use_web_search") else "empty"),
               f"{len(web_raw)} sources")
    trace.soft("Academic Research", "ok" if papers_raw else
               ("skipped" if not plan.get("use_academic_search") else "empty"),
               f"{len(papers_raw)} papers")
    if plan.get("use_web_search") and not web_raw:
        warnings.append("No web sources retrieved — add TAVILY/EXA/SERPAPI "
                        "keys in .env for grounded research.")

    evidence = await trace.run(
        "Source Credibility",
        source_credibility_agent.run(topic, web_raw, papers_raw,
                                     time_sensitive),
        lambda e: f"kept {len(e.get('web', []))} web / "
                  f"{len(e.get('papers', []))} papers · "
                  f"{e.get('credibility_note','')[:100]}")

    # ---- parallel lane 1: current facts prefetch ∥ visual reference hunt
    image_count = int(options.get("image_count", s.default_min_images))

    lane1 = []
    if time_sensitive:
        lane1.append(trace.run(
            "Current Facts Prefetch",
            currentness_output_guard.prefetch_current_facts(topic, plan,
                                                            analysis),
            lambda r: f"{len(r[0])} verified current facts from "
                      f"{len(r[1])} fresh official-leaning sources"))
    else:
        trace.soft("Current Facts Prefetch", "skipped",
                   "topic not time-sensitive")
        lane1.append(asyncio.sleep(0, result=([], [])))
    if image_count > 0:
        lane1.append(trace.run(
            "Visual Reference Hunt",
            visual_reference_agent.run(
                topic, analysis.get("domain", "general"), brief,
                [sec["title"] for sec in outline["sections"]], image_count),
            lambda r: f"{len(r)} verified reference candidates (incl. spares)"))
    else:
        trace.soft("Visual Reference Hunt", "skipped", "images set to 0")
        lane1.append(asyncio.sleep(0, result=[]))
    r1 = await asyncio.gather(*lane1, return_exceptions=True)
    fact_sheet, fresh_official = _safe(r1[0], ([], []))
    references = _safe(r1[1], [])

    if fresh_official:
        seen_urls = set()
        merged = []
        for r in fresh_official + evidence.get("web", []):
            u = (r.get("url") or "").split("#")[0].rstrip("/")
            if u and u not in seen_urls:
                seen_urls.add(u)
                merged.append(r)
        evidence["web"] = merged[:14]
    if time_sensitive and not fact_sheet:
        warnings.append("Time-sensitive query, but no verified current facts "
                        "could be extracted — 'latest' claims are flagged for "
                        "official confirmation instead of asserted.")

    # ---- writing (markdown-native, extended thinking, chunked for depth)
    article = await trace.run(
        "Article Writer",
        article_writer_agent.run(topic, analysis, brief, outline,
                                 evidence, options, fact_sheet=fact_sheet),
        lambda a: f"{len(a.get('sections', []))} sections drafted · "
                  f"{len(a.get('key_takeaways', []))} takeaways · "
                  f"{sum(1 for x in a.get('sections', []) if x.get('pull_quote'))} pull quotes")

    article, _, contract_notes = outline_contract_engine.enforce(article, outline)
    if contract_notes:
        trace.soft("Outline Contract Engine (draft pass)", "repaired",
                   "; ".join(contract_notes[:2]))

    # ---- abstract guard (LLM only when the deterministic check trips)
    generic_hits = universal_abstract_guard.is_generic(
        article.get("abstract", ""))
    if generic_hits:
        try:
            article, changed = await trace.run(
                "Abstract Quality Guard",
                universal_abstract_guard.run(article, topic,
                                             analysis.get("domain", "general")),
                lambda r: "abstract rewritten" if r[1] else "abstract passed")
        except Exception:
            trace.soft("Abstract Quality Guard", "skipped",
                       "rewrite failed; draft abstract kept")
    else:
        trace.soft("Abstract Quality Guard", "ok", "abstract passed")

    # ---- ONE combined polish pass (standards + clarity + voice + cohesion)
    if s.premium_quality:
        try:
            article = await trace.run(
                "Scholarly Polish",
                text_enhancer_agent.polish(
                    article, topic, analysis.get("domain", "general"),
                    thread=outline.get("narrative_thread", "")),
                lambda a: "standards + clarity + voice + cohesion in one pass")
            article, _, _ = outline_contract_engine.enforce(article, outline)
        except Exception:
            trace.soft("Scholarly Polish", "skipped",
                       "polish pass failed; draft kept")
    else:
        trace.soft("Scholarly Polish", "skipped", "premium mode off")

    # ---- parallel lane 2: currentness audit ∥ image build
    lane2 = [trace.run(
        "Currentness Output Guard",
        currentness_output_guard.run(article, topic, plan, time_sensitive,
                                     fresh=fresh_official or None),
        lambda r: r[1].get("note", r[1].get("status", ""))[:150])]
    if image_count > 0:
        lane2.append(trace.run(
            "Image Embedder",
            image_regeneration_agent.run(topic, outline, references,
                                         image_count),
            lambda r: f"{len(r[0])} images embedded · {r[1][:110]}"))
    else:
        trace.soft("Image Embedder", "skipped", "Images disabled.")
        lane2.append(asyncio.sleep(0, result=([], "Images disabled.")))
    r2 = await asyncio.gather(*lane2, return_exceptions=True)
    article, current_verdict = _safe(
        r2[0], (article, {"status": "unverified",
                          "note": "Currentness check errored — confirm "
                                  "time-sensitive values from official docs."}))
    images, image_status = _safe(r2[1], ([], "Image build failed — see trace."))
    if images or image_status == "Images disabled.":
        ref_n = sum(1 for i in images if i["kind"] == "reference")
        gen_n = len(images) - ref_n
        image_relevance = (f"{ref_n} reference / {gen_n} generated visuals — "
                           "all embedded and topic-linked"
                           if images else "images off")
    else:
        image_relevance = "image build failed"
        warnings.append("Image build failed — article delivered without "
                        "figures; see the agent trace for details.")

    currentness_status = current_verdict.get("status", "not_required")
    if currentness_status == "unverified":
        warnings.append("Time-sensitive values could not be verified against "
                        "official sources — confirm exact current values from "
                        "official docs/API before relying on them.")

    # ---- ONE quality validator (facts + topic + intent in a single audit)
    outline_titles = [sec["title"] for sec in outline["sections"]]
    verdict = await trace.run(
        "Quality Validator",
        quality_validator_agent.run(
            article, evidence, topic,
            query_lock=analysis.get("query_lock", ""),
            adjacent=analysis.get("adjacent_topics_to_avoid", []),
            answer_contract=brief.get("answer_contract", []),
            outline_titles=outline_titles,
            intent=analysis.get("intent", "what")),
        lambda v: f"facts={v['facts'].get('status')} · "
                  f"topic {v['topic'].get('topic_alignment')} · "
                  f"intent={v['intent'].get('status')}")
    fact = verdict["facts"]
    topicv = verdict["topic"]
    intentv = verdict["intent"]
    if fact.get("issues"):
        article = quality_validator_agent.apply_fixes(article, verdict)
    for sug in (intentv.get("out_of_scope_suggestions") or [])[:3]:
        warnings.append(f"Outline-level suggestion: {sug}")

    # ---- targeted corrective rewrite: hard fail OR sub-target alignment
    topic_score = float(topicv.get("topic_alignment") or 0)
    needs_repair = (topicv.get("status") == "fail"
                    or intentv.get("status") == "fail"
                    or topic_score < 80)
    if needs_repair:
        trace.soft("Corrective Rewrite", "running",
                   f"topic alignment {topic_score} — targeted repair pass "
                   "against query lock")
        repair_notes = {
            "query_lock": analysis.get("query_lock", ""),
            "prohibited_adjacent_topics":
                analysis.get("adjacent_topics_to_avoid", []),
            "drift_sections": topicv.get("drift_sections", []),
            "drift_notes": topicv.get("drift_notes", []),
            "missing_contract_items":
                topicv.get("missing_contract_items", []),
            "missing_answer_elements": intentv.get("missing", []),
        }
        repaired = False
        for repair_role in ("editor", "writer"):
            try:
                article = await text_enhancer_agent.run(
                    article, topic, repair_notes=repair_notes,
                    role=repair_role)
                repaired = True
                break
            except Exception as exc:
                trace.soft("Corrective Rewrite", "error",
                           f"{repair_role}-chain repair failed: "
                           f"{type(exc).__name__}: {str(exc)[:170]}")
        if repaired:
            article, _, _ = outline_contract_engine.enforce(article, outline)
            verdict = await trace.run(
                "Quality Validator (post-repair)",
                quality_validator_agent.run(
                    article, evidence, topic,
                    query_lock=analysis.get("query_lock", ""),
                    adjacent=analysis.get("adjacent_topics_to_avoid", []),
                    answer_contract=brief.get("answer_contract", []),
                    outline_titles=outline_titles,
                    intent=analysis.get("intent", "what")),
                lambda v: f"topic {v['topic'].get('topic_alignment')} · "
                          f"intent={v['intent'].get('status')}")
            fact = verdict["facts"]
            topicv = verdict["topic"]
            intentv = verdict["intent"]
            if fact.get("issues"):
                article = quality_validator_agent.apply_fixes(article, verdict)
            topic_score = float(topicv.get("topic_alignment") or topic_score)
        else:
            warnings.append("Corrective rewrite failed on both the editor "
                            "and writer chains — flagged items left as-is; "
                            "the agent trace has the exact provider errors.")

    # ---- hard outline contract (final) + pre-publish gate
    article, alignment, final_notes = outline_contract_engine.enforce(article, outline)
    trace.soft("Hard Outline Contract Editor", "ok",
               f"alignment {alignment} " +
               ("· " + "; ".join(final_notes[:2]) if final_notes else ""))

    gate_pass = (alignment >= 70
                 and topic_score >= 80
                 and topicv.get("status") != "fail"
                 and fact.get("status") != "fail")
    validation_status = (f"PASS · topic alignment {topic_score:.0f}/100"
                         if gate_pass else
                         f"PASS WITH WARNINGS · topic alignment "
                         f"{topic_score:.0f}/100")
    if not gate_pass:
        warnings.append("Pre-publish gate found unresolved issues — output "
                        "shown with warnings rather than blocked, since one "
                        "repair pass already ran.")
    elif topic_score < 90:
        warnings.append(f"Topic alignment {topic_score:.0f}/100 — passable "
                        "but below the 90+ target; consider regenerating "
                        "with a more specific query.")
    trace.soft("Pre-Publish Validation Gate", "ok" if gate_pass else "warn",
               f"outline={alignment} · topic={topic_score:.0f} "
               f"· facts={fact.get('status')} · currentness={currentness_status} "
               f"· {time.perf_counter() - t0:.0f}s wall")

    final = final_formatter_agent.assemble(topic, outline, article, images,
                                           evidence, fact_sheet=fact_sheet)

    diagnostics = {
        "agents_used": [t["agent"] for t in trace.steps
                        if t["status"] in ("ok", "repaired", "warn", "reused")],
        "validation_status": validation_status,
        "outline_alignment_score": alignment,
        "source_credibility_status": evidence.get("credibility_note",
                                                  "n/a")[:200],
        "currentness_status": currentness_status,
        "image_relevance_status": image_relevance,
        "warnings": list(dict.fromkeys(warnings)),
        "trace": trace.steps,
    }
    return {"article": final, "diagnostics": diagnostics}
