"""Image Generation / Referential Image Agent — embed-or-replace guarantee.

Every image that ships in the article is DOWNLOADED server-side and embedded
as a data: URI. Dead links, hotlink-blocked hosts and CORS problems can no
longer silently drop figures in the browser or the PDF. If a reference image
fails to download, the next verified spare takes its slot; if spares run out,
a topic-specific generated visual fills it — so the delivered image count
always equals the requested count.

Modes:
  referential    — verified reference images first, generated fill the gap.
  regenerated    — every slot generated (provider image model if configured,
                   deterministic SVG engine otherwise).
  smart_fallback — same as referential.
  off            — no images.
"""
from __future__ import annotations

import asyncio
import base64
import difflib
import json
from typing import Optional

import httpx

from ..config import get_settings
from ..services import deterministic_visual_engine as dve
from ..services.llm_gateway import chat_json

MAX_IMAGE_BYTES = 6_500_000
DOWNLOAD_TIMEOUT = 18.0
GEN_TIMEOUT = 45.0

PLAN_SYSTEM = """You are the Visual Planning Agent inside SEARCH AI. Plan the
explanatory visuals for an article. For each requested slot, pick the single
best visual archetype for the topic + section and give exact labels/data so a
deterministic renderer can draw it. Archetypes:
- loss_curves (training vs validation curves; overfitting/complexity topics)
- error_complexity (bias-variance / model-complexity U-curve)
- distribution (PMF/PDF/CDF-style curve or histogram)
- timeline (ordered dated events)
- flowchart (process/attack path/clinical workflow, 3-7 steps)
- architecture (labelled block diagram, 3-6 blocks with connections)
- comparison_bars (labelled bar chart with values)
- cycle (circular process, 3-6 phases)
- confusion_matrix (2x2 with TP/FP/FN/TN style labels)
- time_series (line chart of a quantity over time)
Return JSON:
{"visuals": [{"slot": n, "archetype": "...",
  "title": "figure title specific to topic",
  "caption": "reader-facing caption",
  "explanation": "1-2 sentences on what the figure shows",
  "section_id": "outline section id it belongs to",
  "data": { ... archetype-specific ... }}]}
data shapes:
 loss_curves: {"x_label","y_label"}
 error_complexity: {}
 distribution: {"kind":"pmf|pdf|cdf","x_label","points":[[x,y],...] optional}
 timeline: {"events":[{"label","year_or_date"}...]}
 flowchart: {"steps":["..."], "branch": optional {"from": idx, "label","to_label"}}
 architecture: {"blocks":["..."], "edges":[[i,j],...]}
 comparison_bars: {"labels":["..."], "values":[n...], "y_label"}
 cycle: {"phases":["..."]}
 confusion_matrix: {"labels":{"tp","fp","fn","tn"}, "axis":["Predicted","Actual"]}
 time_series: {"x_label","y_label","series":[{"name","points":[[x,y]...]}]}
HONESTY RULES:
- Labels must be lifted from the article's actual concepts (the section
  titles and subpoints supplied) — generic placeholders like
  Client/Service/Store, Input/Process/Output or Phase 1..4 are failures.
- NEVER invent quantitative data: no bar/line/comparison charts with
  made-up values or scores. Choose numeric archetypes ONLY when the
  supplied material contains real numbers; otherwise use structural
  archetypes (flowchart, architecture, timeline, cycle, matrix) whose
  content is conceptual, not numeric.
All labels must be specific to THIS topic. No two visuals may share an
archetype unless unavoidable."""


# ------------------------------------------------------------ helpers
async def download_data_uri(url: str) -> Optional[str]:
    """Fetch an image and return it as a data: URI, or None on any failure."""
    if not url:
        return None
    if url.startswith("data:image/"):
        return url
    if not url.startswith(("http://", "https://")):
        return None
    try:
        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT,
                                     follow_redirects=True) as c:
            r = await c.get(url, headers={"User-Agent": "SEARCH-AI/1.0",
                                          "Accept": "image/*,*/*;q=0.8"})
            r.raise_for_status()
            ct = (r.headers.get("content-type") or "").split(";")[0].strip()
            if not ct.startswith("image/") or "svg" in ct and b"<script" in r.content[:4096].lower():
                return None
            if len(r.content) < 1500 or len(r.content) > MAX_IMAGE_BYTES:
                return None
            return f"data:{ct};base64,{base64.b64encode(r.content).decode()}"
    except Exception:
        return None


def _hint_to_id(hint: str, outline: dict) -> str:
    ids = [s["id"] for s in outline.get("sections", [])]
    if hint in ids:
        return hint
    if not hint:
        return ""
    best, best_r = "", 0.0
    for s in outline.get("sections", []):
        r = difflib.SequenceMatcher(None, hint.lower(),
                                    s["title"].lower()).ratio()
        if r > best_r:
            best, best_r = s["id"], r
    return best if best_r >= 0.4 else ""


async def plan_generated_visuals(topic: str, outline: dict,
                                 slots: list[int],
                                 hints: list[str]) -> list[dict]:
    if not slots:
        return []
    titles = [{"id": s["id"], "title": s["title"]}
              for s in outline["sections"]]
    user = (f"Topic: {topic}\nSections: {json.dumps(titles)}\n"
            f"Slots to fill: {slots}\n"
            f"Hints for these slots: {json.dumps(hints)}\n"
            "Plan one visual per slot.")
    try:
        plan = await chat_json("writer", PLAN_SYSTEM, user,
                               max_tokens=2400, temperature=0.4)
        return plan.get("visuals", [])
    except Exception:
        return []


async def _gemini_image(model: str, prompt: str) -> Optional[str]:
    s = get_settings()
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={s.gemini_api_key}")
    payload = {"contents": [{"parts": [{"text": prompt}]}],
               "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]}}
    async with httpx.AsyncClient(timeout=GEN_TIMEOUT) as c:
        r = await c.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
    for part in data["candidates"][0]["content"]["parts"]:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            mime = inline.get("mimeType") or inline.get("mime_type", "image/png")
            return f"data:{mime};base64,{inline['data']}"
    return None


async def _openai_image(model: str, prompt: str) -> Optional[str]:
    s = get_settings()
    async with httpx.AsyncClient(timeout=GEN_TIMEOUT) as c:
        r = await c.post("https://api.openai.com/v1/images/generations",
                         headers={"Authorization": f"Bearer {s.openai_api_key}"},
                         json={"model": model, "prompt": prompt,
                               "size": "1024x1024", "n": 1})
        r.raise_for_status()
        data = r.json()
    item = data["data"][0]
    if item.get("b64_json"):
        return f"data:image/png;base64,{item['b64_json']}"
    if item.get("url"):
        return await download_data_uri(item["url"])
    return None


def _gen_combos() -> list[tuple[str, str]]:
    """First two (provider, model) pairs — bounded so a bad image model
    never stalls the pipeline for minutes."""
    s = get_settings()
    combos: list[tuple[str, str]] = []
    for provider in s.image_provider_order:
        if provider == "gemini" and not s.gemini_api_key:
            continue
        if provider == "openai" and not s.openai_api_key:
            continue
        for model in s.image_model_chain(provider):
            combos.append((provider, model))
    return combos[:2]


async def _generate_one(prompt: str) -> Optional[str]:
    for provider, model in _gen_combos():
        try:
            if provider == "gemini":
                out = await _gemini_image(model, prompt)
            elif provider == "openai":
                out = await _openai_image(model, prompt)
            else:
                out = None
            if out:
                return out
        except Exception:
            continue
    return None


def _svg_visual(archetype: str, topic: str, title: str, data: dict) -> str:
    svg = dve.render(archetype, topic, title, data)
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


# ------------------------------------------------------------ main
async def run(topic: str, outline: dict, references: list[dict],
              image_count: int) -> tuple[list[dict], str]:
    """One intelligent mode: verified reference figures fill the slots,
    topic-specific generated visuals cover any gap. Delivered count always
    equals the requested count. Returns (images, status_note)."""
    if image_count <= 0:
        return [], "Images disabled."
    s = get_settings()
    images: list[dict] = []
    dead_refs = 0

    # ---- referential slots: download-verify each candidate (original URL
    # first, thumbnail as fallback — hotlink-blocked hosts are common),
    # spares step in for anything unreachable.
    via_thumb = 0
    if references:
        async def fetch_ref(r: dict) -> tuple[Optional[str], bool]:
            uri = await download_data_uri(r.get("url", ""))
            if uri:
                return uri, False
            thumb = r.get("thumbnail", "")
            if thumb and thumb != r.get("url"):
                uri = await download_data_uri(thumb)
                if uri:
                    return uri, True
            return None, False

        results = await asyncio.gather(*[fetch_ref(r) for r in references])
        seen: set[str] = set()
        for ref, (uri, from_thumb) in zip(references, results):
            if len(images) >= image_count:
                break
            if not uri:
                dead_refs += 1
                continue
            if from_thumb:
                via_thumb += 1
            key = uri[:120]
            if key in seen:
                continue
            seen.add(key)
            images.append({
                "slot": 0, "url": uri,
                "caption": ref.get("caption", topic)[:220],
                "explanation": ref.get("explanation", "")[:400],
                "source_label": ref.get("source_label", "web"),
                "kind": "reference",
                "section_id": _hint_to_id(ref.get("section_hint", ""), outline),
            })

    # ---- generated fill for any unfilled slots
    missing = image_count - len(images)
    gen_images: list[dict] = []
    if missing > 0:
        slots = list(range(len(images) + 1, image_count + 1))
        sec_titles = [sec["title"] for sec in outline["sections"]]
        hints = [sec_titles[min(i, len(sec_titles) - 1)]
                 for i in range(len(slots))]
        plans = await plan_generated_visuals(topic, outline, slots, hints)

        async def make(idx: int) -> dict:
            plan = plans[idx] if idx < len(plans) else {}
            archetype = plan.get("archetype", "flowchart")
            title = plan.get("title") or topic
            if not plan.get("data"):
                sec_titles = [x["title"] for x in
                              outline.get("sections", [])][:5]
                if sec_titles:
                    plan["data"] = {"steps": sec_titles,
                                    "nodes": sec_titles,
                                    "phases": sec_titles}
            data_uri = None
            kind = "fallback_visual"
            if s.premium_quality:
                prompt = (f"Clean flat professional explanatory {archetype} "
                          f"figure about: {title}. Labelled, white background, "
                          "publication quality, no photo, no people, no text "
                          "walls.")
                data_uri = await _generate_one(prompt)
                if data_uri:
                    kind = "generated"
            if not data_uri:
                data_uri = _svg_visual(archetype, topic, title,
                                       plan.get("data") or {})
                kind = "fallback_visual"
            return {
                "slot": 0, "url": data_uri,
                "caption": plan.get("caption") or f"Explanatory visual — {topic}",
                "explanation": plan.get("explanation", ""),
                "source_label": ("AI-generated figure" if kind == "generated"
                                 else "SEARCH AI visual"),
                "kind": kind,
                "section_id": _hint_to_id(plan.get("section_id", ""), outline),
            }

        gen_images = list(await asyncio.gather(*[make(i)
                                                 for i in range(len(slots))]))
    images += gen_images

    # ---- number slots + spread section assignments deterministically
    sec_ids = [sec["id"] for sec in outline.get("sections", [])]
    assigned = {img["section_id"] for img in images if img["section_id"]}
    free = [i for i in sec_ids if i not in assigned] or sec_ids
    fi = 0
    for i, img in enumerate(images):
        img["slot"] = i + 1
        if not img["section_id"] and sec_ids:
            img["section_id"] = free[fi % len(free)]
            fi += 1

    ref_n = sum(1 for i in images if i["kind"] == "reference")
    gen_n = len(images) - ref_n
    if gen_n == 0:
        status = (f"All {len(images)} slots filled with verified, embedded "
                  "reference images.")
    else:
        status = ("Reference-first visual mode used verified source images "
                  "where available and generated topic-specific explanatory "
                  "visuals for missing slots.")
    fetched = sum(1 for i in images if i["kind"] == "reference")
    if references:
        status += (f" [{fetched}/{len(references)} reference candidates "
                   f"fetched; {via_thumb} via thumbnail; "
                   f"{dead_refs} unreachable replaced]")
    return images[:image_count], status
