# SEARCH AI — Architecture

This document describes every layer, every agent, every deterministic engine, and every feature of the user interface, step by step. It reflects the v2 (consolidated) pipeline at build 2026.07.13-18.

---

## 1. System layers

```
Browser client (SPA)  →  FastAPI server  →  Pipeline orchestrator
        ↓                       ↓                      ↓
  outline editor          API endpoints         2 phases, 3 parallel lanes
  article renderer        image proxy                  ↓
  PDF paginator           no-cache shell     Service layer: LLM gateway ·
                                             search gateway · SVG engine ·
                                             contract engine · exporters
                                                        ↓
                              External: Anthropic / OpenAI / Gemini / compat,
                              Tavily / Exa / SerpAPI, OpenAlex / Crossref
```

**Design principles** (each earned by a real bug): *user options are law* (agents advise, never veto); *the outline is a contract* enforced by code, not prompts; *facts before writing* (verified current facts override model memory); *everything embedded* (images live inside the article data, so view, PDF and Word can never disagree); *register matches the request* (a how-to yields a builder's playbook, a research query a scholarly paper); *the model never invents sources* (a truth boundary bars fabricated tools, products, statistics and versions); *models propose, code disposes* (deterministic reconciliation, contracts, gates); *self-healing at every boundary* (provider chains, model fallbacks, JSON coercion, thumbnail rescue, repair retries).

## 2. The two phases

### Phase 1 — Outline (`POST /api/outline`)

1. **Research Director** *(one LLM call)* — decodes the query into an analysis (query lock, adjacent-topics drift list, domain, intent, audience, time-sensitivity, key entities), a research brief (answer contract, research questions, three-horizon search queries, academic + visual queries, validation criteria), and a retrieval plan (channels, official domains). User toggles override the plan unconditionally.
2. **Outline Architect** — reads the intent to decide register (a how-to or implementation topic gets verb-first, step-oriented sections that walk from setup to working result, each naming the artifact it will deliver; research topics keep analytical titles), then picks the best of 10 adaptive layouts (or your forced choice), produces 6–10 sections with goals, subpoints, per-section **key questions** and a **bridge from the previous section**, plus a one-sentence **narrative thread** the whole article must advance. Tolerates models nesting/renaming the sections array, auto-retries once on an empty result, and raises an actionable error otherwise.

The brief and plan are stashed inside the analysis and travel with the outline back to the client, so Generate never repeats the work.

### Phase 2 — Generate (`POST /api/generate`)

Serial spine with three parallel lanes:

1. **Research Director** (reused from phase 1 when present).
2. **Web Research ∥ Academic Research** — Tavily/Exa/SerpAPI fan-out, merged and deduplicated with official-docs boost; OpenAlex + Crossref blending most-cited seminal papers with the newest publications.
3. **Source Credibility** — prunes off-topic pages, keyword-coincidence papers, SEO listicles, and **fabrication-risk sources** (single-source product/tool/marketplace claims no authoritative source corroborates); emits the credibility note shown in Diagnostics.
4. **Lane 1 (parallel): Current Facts Prefetch ∥ Visual Reference Hunt** — for time-sensitive topics, dated verified facts are extracted from fresh official-leaning sources *before writing* and merged into the evidence; simultaneously, candidate figures are searched and LLM-judged for genuine explanatory value (logos/stock rejected), gathering up to 2× your image count as verified spares.
5. **Article Writer** — markdown-native (see §4), extended thinking enabled, bound to the query lock + outline contract + facts sheet. **Register rule**: how-to/implementation/playbook intents produce a builder's guide — verb-first step headings, a usable artifact in a fenced block per major step (prompt, config, directory tree, schema, checklist), one worked example threaded throughout, mapping tables — while research intents use scholarly register. **Truth boundary**: no tool, product, plugin, statistic, threshold or version is presented as real unless the evidence contains it; illustrative material is framed as reader-created, never given an invented proper-noun name. Plus depth-ladder and flow rules, evidence markers, per-section pull quotes, tables/sub-headings/bold structure, cross-section key takeaways. Outlines longer than 5 sections are written in **two passes** with a verbatim-ending continuity handoff.
6. **Outline Contract Engine** *(deterministic)* — fuzzy-matches sections by id/title, folds extras into their nearest host, restores anything missing, preserves order. Runs after the draft, after polish, and once more before the gate.
7. **Abstract Quality Guard** — deterministic banned-pattern check; only if it trips does an LLM rewrite run.
8. **Scholarly Polish** *(one pass, thinking enabled)* — field standards per domain, clarity, human voice, and **cohesion** (repairs cold section openings against the narrative thread, deepens the thinnest section one ladder rung). Markdown in, markdown out. On failure the draft is kept.
9. **Lane 2 (parallel): Currentness Output Guard ∥ Image Embedder** — the guard audits the finished text against fresh evidence and can rewrite up to two stale sections wholesale; the embedder downloads every accepted reference figure server-side (original URL, then thumbnail fallback), replaces dead links with verified spares, and fills any remaining slots with provider-generated images or deterministic topic-labelled SVG figures. Delivered count always equals requested count; fetch statistics are reported.
10. **Quality Validator** *(one LLM call)* — audits **facts** (against evidence, with sentence-level fixes), **topic integrity** (0–100 rubric: drift, generic sections, cold openings, contract items), and **answer intent** (does a "how" contain a procedure, a comparison a real side-by-side) — all judged *within the approved outline's scope*; out-of-scope gaps become suggestions. Any named tool, product or statistic absent from the evidence is flagged as an **invented entity** with a fix that strips or reframes it. A deterministic reconciler resolves model self-contradictions, then fixes are applied.
11. **Corrective Rewrite** *(conditional)* — only when alignment < 80 or a hard fail: a targeted repair pass through the editor chain, retried through the writer chain, followed by one re-validation. Errors are logged verbatim in the trace.
12. **Pre-Publish Gate** — outline alignment ≥ 70, topic ≥ 80, facts not failed → `PASS · topic alignment N/100`; otherwise pass-with-warnings, never a block. Wall time recorded.
13. **Final Formatter** *(deterministic)* — maps evidence markers to a deduplicated References list (inline markers currently hidden by preference), scrubs stray model references and placeholders, attaches images and takeaways.

## 3. Service layer

- **LLM Gateway** — every call routes by *role* (`research` / `writer` / `editor` / `validator` / `image`) through its provider order, then each provider's model fallback chain. Handles: native JSON mode, thinking-part filtering, array-wrapped-JSON coercion, unparseable-output fallthrough, size-scaled timeouts (60 s / 100 s / 180 s), fail-fast on auth errors, and **extended thinking** for writer/editor calls (budget from `.env`; automatic retry without thinking on a 400).
- **Search Gateway** — web (Tavily, Exa, SerpAPI), academic (OpenAlex, Crossref), and image search (SerpAPI Images, Openverse, Wikimedia), all merged, deduplicated and time-filtered.
- **Deterministic SVG Engine** — ten figure archetypes (timelines, flowcharts, loss curves, architectures, confusion matrices…) drawn from the article's own section labels — never generic Client/Service/Store placeholders, and never charts with invented numbers; carries explicit dimensions so figures rasterize into PDF/Word.
- **Exporters** — `docx` builder (heading hierarchy H1–H3, styled tables, inline bold/italic/code/math, embedded figures with captions, Key Takeaways section, numbered references) and a server-side PDF fallback; the primary PDF path is client-side (§5).
- **Outline Contract Engine, Currentness Guard, Abstract Guard** — described above.

## 4. The delimited-markdown article format

The writer and polish agents exchange articles as plain text — never JSON:

```
=== TITLE ===
=== ABSTRACT ===
=== ANSWER ===
=== TAKEAWAYS ===
- insight …
=== SECTION: s1-slug | Section Title ===
PULL QUOTE: optional single line
markdown body …
```

`parse_article_md` / `serialize_article_md` round-trip this into the article dict used everywhere else. Benefits: dramatically better prose (no string escaping), cheap continuity handoffs between chunked passes, and pull quotes produced by the writer itself instead of a separate agent.

## 5. The browser client, feature by feature (UI walkthrough)

**Step 1 — Topic bar.** Type any topic. **Create Outline** (blue) builds an editable outline first; **Generate** (orange) is enabled the moment a topic exists and runs end-to-end — if no outline exists yet (or the topic changed), it creates one automatically and continues.

**Step 2 — Advanced Options** (chip toggles the panel): **Article format** (Auto + 10 layouts), **Images in article** (0–12; the system decides reference-vs-generated per slot automatically), and two toggles — **Current findings check** (activates facts prefetch + currentness guard) and **Web research**. The **Quality Lock** chip shows whether premium polish is on (from `.env`). The header chip shows provider readiness and the running build number.

**Step 3 — Outline editor.** Title field, layout badge, one card per section: rename inline, edit the goal, edit/add/remove subpoints, reorder with ↑/↓, delete with ✕, **+ Add section**, **↻ Regenerate outline** for a fresh proposal, and **✕ Discard outline** to reject it entirely and return to the topic bar. Hidden metadata (narrative thread, bridges, key questions) is preserved through your edits. The article is contractually bound to whatever you approve.

**Step 4 — Generation.** The status bar shows a live elapsed clock plus a stage ticker naming each pipeline phase as it runs.

**Step 5 — The article.** Title and meta line; **Abstract** card; **Direct answer** card; **Key takeaways** card (cross-section syntheses); numbered section cards with sub-headings, bold key points, striped contained tables, KaTeX math, labelled code boxes, and styled pull quotes; **figures** placed in their sections with captions and source labels (real origin vs "SEARCH AI visual"), click any figure for a full-screen lightbox; a deduplicated **References** list closes the article. Broken images show a visible placeholder rather than silently vanishing.

**Step 6 — Export.** **Download PDF**: the page is cloned into A4 frames block-by-block (a break can never cut a table, figure or code box), SVG figures are pre-rasterized, and each page is captured pixel-perfect with footer page numbers. **Download Word**: real heading hierarchy, tables, inline formatting, embedded images, takeaways and references.

**Step 7 — Diagnostics & Agent Trace.** Cards for validation status (with topic-alignment score), outline alignment, currentness status, image relevance (`4 reference / 2 generated … [9/12 fetched; 3 via thumbnail]`), source credibility, and agents used; yellow banners for warnings and outline-level suggestions; then the full per-agent timeline with millisecond timings and the total wall time in the gate row.

**Reliability chrome** — the build number appears in the terminal banner, page footer and header chip with a mismatch banner; the launcher kills stale servers and opens a cache-proof boot URL; the app shell is served no-cache; overlays are inline-style controlled so a stale stylesheet can never freeze the page.

## 6. Endpoints

`POST /api/outline` · `POST /api/generate` · `POST /api/export/docx` · `POST /api/export/pdf` · `GET /api/health` (status, build, env file) · `GET /api/img` (CORS-safe image proxy).
