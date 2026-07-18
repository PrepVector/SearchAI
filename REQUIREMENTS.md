# SEARCH AI — Requirements Specification

**Version:** v2 · build 2026.07.13-18 · **Status:** implemented and shipping

> This is the product requirements document. The Python package list lives separately at `backend/requirements.txt` (pip dependencies).

---

## 1. What we are building

SEARCH AI is a local, single-user, multi-model AI research engine that turns one typed topic into a premium, outline-bound research article or builder's playbook — grounded in live web + academic evidence, checked against verified current facts, illustrated with real source figures, validated against the user's exact query, and exportable to pixel-perfect PDF and Word.

It runs entirely on the user's machine (FastAPI backend + browser SPA), driven by the user's own API keys. No hosted service, no telemetry.

**Core promise:** the approved outline is a contract, the query is a lock, user options are law, images always match the requested count, "latest" claims are verified before writing, sources are never invented, and every run explains itself in a diagnostics trace.

---

## 2. System outline (the model's structure)

### 2.1 Layers

```
Browser SPA  ->  FastAPI server  ->  Pipeline orchestrator
                                      -> Agent layer (LLM reasoning)
                                      -> Service layer (deterministic)
                                      -> External APIs (LLM + search)
```

### 2.2 Pipeline phases

**Phase 1 — Outline:** Research Director → Outline Architect → user approves / edits / regenerates / **discards**.

**Phase 2 — Generate** (serial spine + 2 parallel lanes):

```
retrieval (web ∥ academic) -> credibility filter
-> LANE 1: current-facts prefetch ∥ visual reference hunt
-> markdown Article Writer (extended thinking, chunked 2-pass)
-> outline contract enforce -> abstract guard (conditional)
-> Scholarly Polish (standards + clarity + voice + cohesion)
-> LANE 2: currentness output guard ∥ image embedder
-> Quality Validator (facts + topic + intent, one audit)
-> corrective rewrite (conditional, editor->writer retry)
-> final contract enforce -> pre-publish gate -> final formatter
```

### 2.3 Agent modules (`backend/app/agents/`)

| Module | Responsibility |
|---|---|
| `research_director_agent` | One call: query analysis (query lock, drift list, domain, intent, time-sensitivity), research brief (answer contract, 3-horizon queries), retrieval plan. User toggles override. |
| `outline_approval_agent` | Adaptive layout (10 types), 6–10 sections with goals/subpoints/key questions/bridges, narrative thread; register-aware (playbook vs analytical); auto-retry; actionable failure. |
| `web_research_agent` | Tavily + Exa + SerpAPI fan-out, merged/deduped, official-docs boost. |
| `academic_research_agent` | OpenAlex + Crossref; seminal + recent blend. |
| `source_credibility_agent` | Prunes off-topic/SEO/**fabrication-risk** sources; single-source product claims dropped. |
| `visual_reference_agent` | Topic-family image queries; LLM judge scores explanatory value; gathers 2× spares. |
| `article_writer_agent` | Delimited-markdown output (no JSON tax), extended thinking, query lock + outline contract + facts override, depth ladder, flow bridges, **register rules**, **truth boundary**, pull quotes, takeaways; chunked 2-pass for >5 sections with verbatim continuity handoff. |
| `text_enhancer_agent` | Scholarly Polish (one pass: field standards, clarity, human voice, cohesion) + targeted corrective-rewrite mode; markdown in/out. |
| `quality_validator_agent` | Single audit: factual issues (incl. **invented-entity** detection) with sentence fixes, topic alignment 0–100 rubric, intent coverage within outline scope; deterministic reconciliation. |
| `image_regeneration_agent` | One intelligent mode: downloads verified references (thumbnail fallback), replaces dead links with spares, fills gaps with generated or deterministic SVG visuals labelled from the article's own concepts; count guarantee. |
| `final_formatter_agent` | Citation marker → deduplicated references mapping, scrubbing, image + takeaway attachment. |

### 2.4 Service modules (`backend/app/services/`)

| Module | Responsibility |
|---|---|
| `llm_gateway` | Role-based provider routing (anthropic/openai/gemini/compatible), per-provider model fallback chains, native JSON mode, thought-part filter, array-JSON coercion, size-scaled timeouts (60/100/180 s), extended-thinking budgets with automatic 400 fallback. |
| `search_gateway` | Web / academic / image search fan-out. |
| `currentness_output_guard` | Facts prefetch BEFORE writing; post-write audit that can rewrite up to 2 stale sections. |
| `outline_contract_engine` | Deterministic section matching, folding, restoration; alignment score. |
| `universal_abstract_guard` | Deterministic generic-abstract detector + conditional LLM rewrite. |
| `deterministic_visual_engine` | 10 SVG archetypes with explicit dimensions, labelled from real content. |
| `docx_export_engine` | Word with H1–H3, tables, inline styles, images, key takeaways, numbered references. |
| `pdf_export_engine` | Server-side fallback (primary PDF is client-side). |

### 2.5 Frontend (`frontend/static/`)

Neumorphic SPA: topic bar, advanced options, outline editor (edit / reorder / add / delete / regenerate / **discard**), live status ticker + elapsed clock, article renderer (abstract, direct answer, key takeaways, numbered sections, KaTeX, tables, code boxes, pull quotes, figures + lightbox, references), block-aware A4 PDF paginator with SVG rasterization, Word download, diagnostics panel, build-stamp + mismatch banner, cache-proof boot.

---

## 3. Inputs

### 3.1 User inputs (UI)

- **topic** — free text, 2–600 chars.
- **options** — `format` ("auto" | 10 named layouts), `current_findings` (bool), `web_research` (bool), `image_count` (int 0–12, delivered count guaranteed).
- **outline edits** — title, section titles/goals/subpoints, order, add/remove; regenerate; **discard**.
- **actions** — Create Outline · Generate (direct mode auto-creates the outline) · Download PDF · Download Word.

### 3.2 Configuration inputs (`backend/.env`)

- Provider keys + model names: `ANTHROPIC_/OPENAI_/GEMINI_/OPENAI_COMPAT_` (`*_API_KEY`, `*_MODEL`, `*_FALLBACK_MODELS`).
- Role orders: `TEXT`/`EDITOR` (default `anthropic,openai,gemini`), `RESEARCH`/`VALIDATOR`/`IMAGE` orders.
- `ENABLE_EXTENDED_THINKING`, `THINKING_BUDGET_TOKENS`.
- Search keys: `TAVILY`/`EXA`/`SERPAPI`; `OPENALEX_EMAIL`, `CROSSREF_EMAIL`.
- `PREMIUM_AI_QUALITY_MODE` (Quality Lock), image model keys (optional).
- `SEARCH_AI_HOST`/`PORT`, `LLM_TIMEOUT_SECONDS`.

### 3.3 External data inputs (runtime)

Web pages/snippets (Tavily, Exa, SerpAPI), academic metadata (OpenAlex, Crossref), image candidates (SerpAPI Images, Openverse, Wikimedia), LLM completions.

### 3.4 API request contracts

| Endpoint | Body |
|---|---|
| `POST /api/outline` | `{ topic, options }` |
| `POST /api/generate` | `{ topic, outline{layout,title,narrative_thread,sections[{id,title,goal,subpoints,key_questions,bridge}]}, analysis, options }` |
| `POST /api/export/docx` | `{ article }` |
| `POST /api/export/pdf` | `{ html, title }` |

---

## 4. Outputs

### 4.1 Article object (primary output)

`topic` · `layout` · `title` · `abstract` (publication-grade, topic-specific) · `executive_answer` (first sentence answers the query) · `key_takeaways[≤7]` (each synthesizes ≥2 sections) · `sections[]` `{ id, title, markdown (tables/###/bold/LaTeX/code), pull_quote? }` · `images[]` `{ slot, url (data URI — always embedded), caption, kind (reference|generated|fallback_visual), source_label, section_id }` · `references[]` `{ title, url, source, year, doi }` (deduplicated).

### 4.2 Diagnostics object

`agents_used[]` · `validation_status` ("PASS · topic alignment N/100" or PASS WITH WARNINGS) · `outline_alignment_score` · `source_credibility_status` · `currentness_status` (current|corrected|unverified|not_required) · `image_relevance_status` ("X reference / Y generated … [A/B fetched; C via thumbnail; D replaced]") · `warnings[]` (incl. outline-level suggestions) · `trace[]` `{agent, status, ms, note}` + wall time.

### 4.3 Files

- **PDF** — client-side block-aware A4 capture; breaks never cut tables, figures or code; footer page numbers; figures rasterized.
- **DOCX** — real heading hierarchy, styled tables, inline bold/italic/code/math, embedded figures with captions, Key Takeaways, numbered references.

### 4.4 Operational outputs

`GET /api/health` → `{ status, build, env_file, provider readiness }`. Terminal banner: build, URL, loaded `.env` path.

---

## 5. Functional requirements (guarantees, all implemented)

- **FR-1** Outline is a hard contract: exact approved sections, exact order, enforced deterministically (alignment scored; extras folded, missing restored).
- **FR-2** Query lock: every stage receives the one question + prohibited adjacent topics; drift is validated and repaired.
- **FR-3** User options are law: agents may advise, never veto (images, web, currentness toggles).
- **FR-4** Verified current facts are fetched BEFORE writing on time-sensitive topics and override model memory; unverified "latest" claims must be flagged, never asserted.
- **FR-5** Image delivery count == requested count; every image embedded as a data URI; dead links auto-replaced; reference-first with generated fill decided automatically.
- **FR-6** Truth boundary: no invented products, tools, plugins, statistics, thresholds or versions; illustrative material must be framed as reader-created; validator flags invented entities; credibility filter drops fabrication-risk sources.
- **FR-7** Register intelligence: how-to/implementation topics produce a builder's playbook (step headings, copy-paste artifacts in fenced blocks, threaded worked example, mapping tables); analytical topics keep scholarly register.
- **FR-8** Depth: two-pass chunked writing for >5 sections with verbatim continuity; depth-ladder rule (claim → mechanism → quantification → implication); evidence floor per section.
- **FR-9** Flow: narrative thread + per-section bridges; cold openings are scored down and repaired; one term per concept.
- **FR-10** Single quality audit (facts/topic/intent) judged within outline scope; deterministic reconciliation; conditional corrective rewrite (editor chain, writer retry) + one revalidation; pre-publish gate (outline ≥70, topic ≥80, facts != fail) — warn, never block.
- **FR-11** Citations: evidence markers map to a deduplicated References list; inline markers hidden (current preference) with clean spacing.
- **FR-12** Outline UX: create, edit everything, reorder, regenerate, **discard**; direct Generate auto-creates the outline.
- **FR-13** Self-verification: single build stamp across terminal/header/footer with mismatch banner; cache-proof boot URL; stale-server kill; diagnostics trace for every run.

---

## 6. Non-functional requirements

- **NFR-1 Local-first:** binds 127.0.0.1; keys never leave the machine except to the chosen providers; `.env` must never be committed.
- **NFR-2 Resilience:** provider/model fallback chains; unparseable or wrongly-shaped model output falls through the chain; failing side-lanes degrade gracefully (soft-skip) instead of aborting the run.
- **NFR-3 Performance:** parallel lanes; size-scaled LLM timeouts (60/100/180 s); typical deep run on a frontier writer ~4–8 min depending on providers.
- **NFR-4 Portability:** Python 3.10–3.14 (incl. free-threaded); pure-Python dependency set; one-click Windows launcher (venv, install, port cleanup, browser open); manual start on any OS.
- **NFR-5 Configurability:** zero hardcoded model names; env aliases for legacy variable names; extended thinking toggleable.
- **NFR-6 Observability:** per-agent millisecond trace, statuses, wall time, warnings — every generation is explainable.

---

## 7. Out of scope (current version)

Multi-user auth/accounts · hosted deployment · non-English UI · direct Google-Docs/Notion publishing · automatic scheduled runs · training or fine-tuning of models (SEARCH AI orchestrates existing provider models) · user-uploaded PDF ingestion (candidate for a future round).
