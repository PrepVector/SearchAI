"""SEARCH AI — FastAPI application.

Endpoints:
  GET  /api/health        provider/config status
  POST /api/outline       phase 1: topic -> editable outline
  POST /api/generate      phase 2: approved outline -> full article
  POST /api/export/docx   article JSON -> Word document
  POST /api/export/pdf    article HTML -> PDF (backend fallback; primary PDF
                          export is the frontend screenshot pipeline)
Static frontend is served from /frontend/static at the site root.
"""
from __future__ import annotations

import io
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

import httpx

from . import pipeline
from .config import BUILD, ENV_FILE, get_settings
from .schemas import (DocxExportRequest, GenerateRequest, GenerateResponse,
                      OutlineRequest, OutlineResponse, PdfExportRequest)
from .services import docx_export_engine, pdf_export_engine
from .services.llm_gateway import LLMError

app = FastAPI(title="SEARCH AI", version="1.0.0",
              description="Premium multi-model AI research article generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


def _safe_filename(title: str, ext: str) -> str:
    base = re.sub(r"[^A-Za-z0-9 _-]+", "", title).strip().replace(" ", "_")
    return f"{(base or 'SEARCH_AI_Article')[:70]}.{ext}"


@app.get("/api/health")
async def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "build": BUILD,
        "env_file": ENV_FILE,
        "text_providers": {p: s.provider_configured(p) for p in
                           ("gemini", "openai", "anthropic", "openai_compatible")},
        "any_text_provider": s.any_text_provider(),
        "search": {"tavily": bool(s.tavily_api_key),
                   "exa": bool(s.exa_api_key),
                   "serpapi": bool(s.serpapi_api_key)},
        "academic": {"openalex": True, "crossref": True},
        "image_generation": {"gemini": bool(s.gemini_api_key and s.gemini_image_model),
                             "openai": bool(s.openai_api_key and s.openai_image_model)},
        "backend_pdf_fallback": pdf_export_engine.available(),
        "premium_quality_mode": s.premium_quality,
        "referential_images": s.enable_referential_images,
    }


@app.post("/api/outline", response_model=OutlineResponse)
async def create_outline(req: OutlineRequest):
    s = get_settings()
    if not s.any_text_provider():
        raise HTTPException(
            status_code=503,
            detail="No LLM provider configured. Open the .env file and set at "
                   "least one API key AND its model name (e.g. GEMINI_API_KEY "
                   "+ GEMINI_MODEL), then restart SEARCH AI.")
    try:
        result = await pipeline.build_outline(req.topic.strip(),
                                              req.options.model_dump())
        return result
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500,
                            detail=f"Outline pipeline failed: {exc}") from exc


@app.post("/api/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    s = get_settings()
    if not s.any_text_provider():
        raise HTTPException(
            status_code=503,
            detail="No LLM provider configured. Open the .env file and set at "
                   "least one API key AND its model name, then restart SEARCH AI.")
    outline = req.outline.model_dump()
    if not outline.get("sections"):
        raise HTTPException(status_code=422,
                            detail="The approved outline has no sections.")
    try:
        result = await pipeline.generate_article(
            req.topic.strip(), outline, req.analysis,
            req.options.model_dump())
        return result
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500,
                            detail=f"Generation pipeline failed: {exc}") from exc


@app.post("/api/export/docx")
async def export_docx(req: DocxExportRequest):
    try:
        data = docx_export_engine.build_docx(req.article.model_dump())
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500,
                            detail=f"Word export failed: {exc}") from exc
    filename = _safe_filename(req.article.title, "docx")
    return StreamingResponse(
        io.BytesIO(data),
        media_type=("application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.document"),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.post("/api/export/pdf")
async def export_pdf(req: PdfExportRequest):
    if not pdf_export_engine.available():
        raise HTTPException(
            status_code=501,
            detail="Backend PDF fallback (WeasyPrint) is not installed. Use "
                   "the in-browser Download PDF button, which captures the "
                   "live article exactly as rendered. To enable the fallback: "
                   "pip install weasyprint")
    data = pdf_export_engine.render_pdf(req.html, req.title)
    if not data:
        raise HTTPException(status_code=500, detail="PDF rendering failed.")
    return StreamingResponse(
        io.BytesIO(data), media_type="application/pdf",
        headers={"Content-Disposition":
                 f'attachment; filename="{_safe_filename(req.title, "pdf")}"'})


@app.get("/api/img")
async def proxy_image(u: str):
    """Same-origin image proxy so the in-browser PDF capture can draw
    external reference images without CORS taint, and so hotlink-blocked
    hosts still render. Images only, 10 MB cap."""
    if not (u.startswith("http://") or u.startswith("https://")):
        raise HTTPException(status_code=400, detail="http(s) URLs only")
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
            r = await c.get(u, headers={"User-Agent": "SEARCH-AI/1.0"})
            r.raise_for_status()
            ct = (r.headers.get("content-type") or "").split(";")[0].strip()
            if not ct.startswith("image/"):
                raise HTTPException(status_code=415,
                                    detail=f"not an image ({ct or 'unknown'})")
            data = r.content
            if len(data) > 10_000_000:
                raise HTTPException(status_code=413, detail="image too large")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502,
                            detail=f"image fetch failed: {exc}") from exc
    return Response(content=data, media_type=ct or "image/jpeg",
                    headers={"Cache-Control": "public, max-age=86400",
                             "Access-Control-Allow-Origin": "*"})


@app.middleware("http")
async def no_cache_shell(request, call_next):
    """The app shell must never be cached — a stale index/app.js is how
    old builds haunt the browser."""
    resp = await call_next(request)
    path = request.url.path
    if path == "/api/img":
        return resp                      # proxied images may cache
    if path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    else:
        # may be stored but MUST revalidate — this lets a fresh fetch
        # overwrite any ancient heuristically-cached copy for good
        resp.headers["Cache-Control"] = "no-cache"
    return resp


# ---- static frontend --------------------------------------------------------
_STATIC = Path(__file__).resolve().parents[2] / "frontend" / "static"
if _STATIC.exists():
    @app.get("/", include_in_schema=False)
    async def index_page():
        return FileResponse(_STATIC / "index.html")

    app.mount("/", StaticFiles(directory=str(_STATIC), html=True),
              name="frontend")
