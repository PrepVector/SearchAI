# SEARCH AI

**A local, multi-model AI research engine that turns any topic into a premium, outline-bound research article or builder's playbook — grounded in live evidence, illustrated with verified figures, and exportable to pixel-perfect PDF and Word.**

Type a topic. Approve, edit, regenerate, or discard the proposed outline — or just press **Generate** and let it run end to end. A consolidated agent pipeline researches the web and academic literature, drafts in pure markdown with extended thinking, matches the register your topic actually needs, refuses to invent sources, validates itself against your exact query, embeds verified images, and hands you a finished article.

Runs entirely on your machine. Bring your own API keys. No hosted service, no telemetry.

---

## Why the output reads like a frontier chat model — and then some

SEARCH AI was rebuilt around one idea: *let the frontier models write the way they write best, then hold the result to contracts no chat app enforces.*

- **Fable-first writing** — the writer and editor default to `anthropic → openai → gemini`, so Claude-class models draft and polish while fast, cheap models handle research and validation.
- **No JSON tax** — the writer produces pure delimited markdown, not escaped JSON. Prose quality is measurably higher outside JSON string-encoding.
- **Extended thinking** — writing and polishing calls carry a thinking budget, so the model plans before it drafts (auto-disabled per model if unsupported).
- **Register intelligence** — a how-to / implementation topic produces a real **builder's playbook** (verb-first steps, copy-paste artifacts in fenced blocks, one worked example threaded throughout, mapping tables); a research topic gets a scholarly analyst register. The costume matches the occasion.
- **Truth boundary** — the writer never presents a tool, product, plugin, statistic, threshold or version as real unless the evidence contains it; illustrative material is framed as reader-created. Credibility filtering and the validator both hunt invented entities.
- **Chunked two-pass writing** — long outlines are written in two halves with a verbatim continuity handoff, so the output-token ceiling never silently truncates depth.
- **Depth ladder + narrative thread** — every major claim descends claim → mechanism → quantification → implication; every section opens by advancing from the previous one's endpoint.
- **And the contracts** — query lock, deterministic outline contract, verified current facts injected *before* writing, a combined quality audit with a corrective-rewrite loop, and a pre-publish gate. A chat one-shot can't do any of that.

## Feature highlights

- **One Research Director** call decodes the query (query lock, drift list, domain, intent, time-sensitivity), writes the research brief (answer contract, three-horizon search queries), and plans retrieval — user toggles always override its plan.
- **Grounded research**: Tavily + Exa + SerpAPI merged and credibility-filtered; OpenAlex + Crossref blending seminal papers with the latest publications; official-docs prioritization; fabrication-risk sources dropped.
- **Current Facts Prefetch**: for time-sensitive topics, verified dated facts are fetched *before* writing and override the model's training memory.
- **Editable outline** with adaptive layouts, per-section bridges and key questions, and a narrative thread. Review it, edit anything, reorder, **↻ Regenerate**, or **✕ Discard** — and once approved it is a **hard contract** enforced by deterministic code.
- **One intelligent image mode**: verified web figures are hunted, LLM-judged for explanatory value, downloaded server-side (thumbnail fallback rescues hotlink-blocked originals), and embedded into the article itself; generated topic-specific visuals — labelled from the article's own concepts, never generic placeholders or invented charts — fill any gap. Delivered count always equals your setting.
- **One Quality Validator** audits facts, topic integrity (0–100), and answer intent in a single pass — judged within your outline's scope, with deterministic reconciliation, invented-entity detection, and a conditional corrective-rewrite loop.
- **Exports**: block-aware A4 PDF (page breaks never cut a table, figure or code block) and Word with real heading hierarchy, styled tables, embedded images, a key-takeaways section and numbered references.
- **Diagnostics & Agent Trace**: per-agent timings, validation scores, image fetch statistics, warnings, and total wall time — every run explains itself.

---

## Quick start (Windows — one click)

1. **Download / clone** this repository.
2. Copy `backend/.env.example` → `backend/.env` and paste **at least one** text provider (API key **and** model name). For the best prose, set an Anthropic key.
3. Double-click **`START_SEARCH_AI.bat`**.

The launcher creates a virtual environment, installs dependencies, stops any stale server on the port, starts the backend, and opens your browser at a cache-proof URL. The terminal banner prints the build number, port, and exactly which `.env` was loaded.

> Requires **Python 3.10+** (tested up to 3.14 free-threaded). Avoid the Microsoft Store Python stub — install from [python.org](https://www.python.org/downloads/) with **Add to PATH** ticked.

### Manual start (any OS)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    # then edit it
python run.py
```

Open the URL shown in the terminal (default `http://127.0.0.1:8025`).

---

## Configuration (`backend/.env`)

Everything is environment-driven — no model names are hardcoded anywhere.

| Group | Variables | Notes |
|---|---|---|
| Text providers | `ANTHROPIC_API_KEY` + `ANTHROPIC_MODEL`, `OPENAI_*`, `GEMINI_*`, `OPENAI_COMPAT_*` | At least one pair required |
| Fallback chains | `*_FALLBACK_MODELS` | Comma-separated, tried in order |
| Role routing | `TEXT_PROVIDER_ORDER`, `EDITOR_PROVIDER_ORDER` (default `anthropic,openai,gemini`), `RESEARCH_PROVIDER_ORDER`, `VALIDATOR_PROVIDER_ORDER`, `IMAGE_PROVIDER_ORDER` | Premium prose from writer/editor; speed from research/validation |
| Premium prose | `ENABLE_EXTENDED_THINKING` (default true), `THINKING_BUDGET_TOKENS` (default 4096) | Think before writing/polishing |
| Web research | `TAVILY_API_KEY`, `EXA_API_KEY`, `SERPAPI_API_KEY` | Any subset; SerpAPI also powers image search |
| Academic | `OPENALEX_EMAIL`, `CROSSREF_EMAIL` | Keyless polite-pool |
| Images | `GEMINI_IMAGE_MODEL` / `OPENAI_IMAGE_MODEL` + fallbacks | Optional; deterministic SVG engine covers gaps |
| Quality | `PREMIUM_AI_QUALITY_MODE` (Quality Lock) | Enables the polish pass |
| Server | `SEARCH_AI_HOST`, `SEARCH_AI_PORT`, `LLM_TIMEOUT_SECONDS` | Launcher reads the port |

Legacy variable names from earlier builds are accepted as aliases.

---

## Using it

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for the full UI walkthrough and agent-by-agent internals, and **[REQUIREMENTS.txt](REQUIREMENTS.txt)** for the complete product specification (inputs, outputs, functional requirements).

The short version: type a topic → **Create Outline** (edit / reorder / ↻ Regenerate / ✕ Discard) or press **Generate** directly → watch the live stage ticker and elapsed clock → read the article (abstract, direct answer, key takeaways, numbered sections, figures with source labels and lightbox, references) → **Download PDF / Word** → open **Diagnostics** to see exactly what every agent did.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Launcher closes instantly | Extract the ZIP fully; don't run from inside the archive. |
| `Python was not found` | Install full Python from python.org with **Add to PATH**. |
| "no LLM key" warning | The banner shows which `.env` loaded — set a key **and** model there, restart. |
| Build mismatch banner | Close old `127.0.0.1` tabs; the launcher's boot URL bypasses stale cache. Header, footer and terminal must show the same build. |
| "Writer produced no sections" | A model ignored the output format — the chain retries automatically; add fallback models in `.env`. |
| Few reference images | Diagnostics shows fetch stats; add `SERPAPI_API_KEY` for the strongest image search. |

## Security

`backend/.env` holds live API keys — **never commit it**. Add a `.gitignore` before your first commit:

```gitignore
backend/.env
backend/.venv/
__pycache__/
*.pyc
```

The app binds to `127.0.0.1` and is intended for local, single-user use. A key pushed to a public repo should be considered compromised and rotated.

## License

MIT — see [`LICENSE`](LICENSE). (Create this file when setting up the repo, or ask and one will be generated.)

---

*Built with FastAPI, httpx, python-docx, marked.js, KaTeX, html2canvas and jsPDF — and a great deal of adversarial debugging.*
