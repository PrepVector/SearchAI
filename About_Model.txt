============================================================
 SEARCH AI — premium multi-model research article generator
============================================================

 NOTE — THIS COPY IS ALREADY CONFIGURED
 --------------------------------------
 backend\.env is pre-filled with your API keys (Gemini, OpenAI,
 Anthropic, Tavily, Exa, SerpAPI), your model fallback chains and
 port 8025. You can double-click START_SEARCH_AI.bat right away.
 Each provider tries its primary model, then each model in
 *_FALLBACK_MODELS, then the next provider in the role order —
 so a renamed/retired model name never blocks generation.
 Keep this folder private: .env contains live secret keys.


WHAT IT DOES
------------
Type any topic. SEARCH AI:
 1. Analyses the query (intent, domain, time-sensitivity).
 2. Proposes an editable outline you approve.
 3. Runs a 20+ agent pipeline: web + academic research,
    source credibility filtering, outline-bound writing,
    domain-standard enforcement, enhancement + humanizing,
    pull quotes, code boxes, referential/generated figures,
    currentness guard, and three validators.
 4. Renders a polished article (math, tables, code, figures)
    and exports it as PDF (screenshot-exact) or Word.
A Diagnostics & Agent Trace panel shows every agent, its
status, timing and the validation verdicts.

QUICK START (Windows)
---------------------
 1. Install Python 3.10+  →  https://www.python.org/downloads/
    (tick "Add Python to PATH" during install)
 2. Double-click  START_SEARCH_AI.bat
    - First run creates a virtual env, installs dependencies
      and opens backend\.env in Notepad.
 3. In backend\.env paste at least ONE text provider —
    an API key AND its model name. Any one of:
       GEMINI_API_KEY    + GEMINI_MODEL
       OPENAI_API_KEY    + OPENAI_MODEL
       ANTHROPIC_API_KEY + ANTHROPIC_MODEL
       OPENAI_COMPAT_*   (Groq / Together / OpenRouter / Ollama…)
    Model names are never hardcoded — you control them here.
 4. Run START_SEARCH_AI.bat again. The browser opens at
    http://127.0.0.1:8025   (port comes from backend\.env)

RECOMMENDED (better research quality)
-------------------------------------
 - TAVILY_API_KEY or EXA_API_KEY or SERPAPI_API_KEY
   → live web research + verified reference images
 - OPENALEX_EMAIL / CROSSREF_EMAIL (just your email)
   → faster academic paper retrieval
 - GEMINI_IMAGE_MODEL or OPENAI_IMAGE_MODEL
   → "Regenerated" image mode uses a real image model;
     without one, SEARCH AI draws deterministic explanatory
     SVG figures (loss curves, timelines, flowcharts, …).

EXPORTS
-------
 - PDF  : in-browser screenshot capture (html2canvas + jsPDF)
          — the PDF matches the on-screen article exactly.
          Backend fallback: pip install weasyprint
 - Word : python-docx export preserving headings, tables,
          images, captions, code and references.
          Optional: pip install cairosvg  → embeds SEARCH AI
          SVG visuals as images inside the .docx too.

TROUBLESHOOTING
---------------
 - "No LLM provider configured"  → fill key + model in
   backend\.env and restart the launcher.
 - Port busy → change SEARCH_AI_PORT in backend\.env.
 - No web sources → add a search key (Tavily is free-tier).
 - Behind a proxy/offline → the app still writes articles
   from model knowledge, and flags anything time-sensitive
   as needing official confirmation.

FOLDER MAP
----------
 SEARCH_AI/
   START_SEARCH_AI.bat      one-click launcher
   README_FIRST.txt         this file
   backend/
     run.py                 server entry (python run.py)
     requirements.txt
     .env.example           copy to .env and fill in
     app/
       main.py              FastAPI endpoints
       pipeline.py          agent orchestration + trace
       agents/              16 specialised agents
       services/            gateways, engines, exporters
   frontend/static/         neumorphic UI (served by backend)
