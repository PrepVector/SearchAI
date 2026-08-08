#!/usr/bin/env python3
"""SEARCH AI -- Claude Code Edition -- local browser dashboard.

A thin, stdlib-only wrapper around the `claude` CLI's own headless mode
(`claude -p ... --output-format json`, `--resume <session_id>`). It does
NOT replace /run-research inside a Claude Code session -- it drives the
exact same command from outside, so a topic box + START button in a
browser tab can do what typing `/run-research <topic>` in the terminal
does, including showing you the outline to approve/edit/regenerate
before anything is written in full.

Why this exists: /run-research already works fine typed directly into
Claude Code. This is for people who'd rather click a button and watch a
progress bar than type slash commands -- purely a convenience layer, not
a required part of the pipeline.

Honesty note: this is new and far less road-tested than /run-research
itself. It depends on two documented but non-trivial CLI behaviors
(`--output-format json`'s exact fields, and `--resume` correctly
continuing a conversation that stopped at the outline checkpoint). If
anything here seems stuck, wrong, or the outline never appears, the
terminal is always the ground truth and the fallback: run
`claude --resume <session_id>` (shown in the debug panel) and continue
the conversation by hand from there. Nothing this script does is
required for /run-research to work on its own.

Prerequisites (see REQUIRED.txt):
  - `claude` must be on PATH and already logged in.
  - This project folder must already be "trusted" by Claude Code -- if
    you haven't run `claude` interactively in this exact folder since
    .claude/settings.json was added, do that once first (accept the
    folder-trust prompt if one appears). Headless mode (-p) cannot show
    that prompt itself, so permission rules are silently ignored until
    the folder has been trusted at least once interactively.

Usage:
    python3 ui/server.py [--port 8787]

Then open http://127.0.0.1:8787 in a browser (it also opens
automatically). Press Ctrl+C in the terminal to stop the server.
"""
from __future__ import annotations

import json
import mimetypes
import re
import subprocess
import sys
import threading
import time
import traceback
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = PROJECT_ROOT / "research_runs"
CLAUDE_BIN = "claude"
DEFAULT_TIMEOUT_S = 1800  # 30 minutes -- generous; real research + repair passes take a while

RUNS: dict[str, dict] = {}
RUNS_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Run-folder inspection -- used only for a cosmetic "what stage is this on"
# hint while a headless `claude -p` call is blocking in the background.
# Never authoritative; the actual state transitions come from whether the
# subprocess has exited, not from file presence.
# ---------------------------------------------------------------------------

def _snapshot_run_dirs() -> set[str]:
    if not RUNS_DIR.exists():
        return set()
    return {p.name for p in RUNS_DIR.iterdir() if p.is_dir()}


def _find_new_run_dir(before: set[str]) -> Path | None:
    if not RUNS_DIR.exists():
        return None
    candidates = [p for p in RUNS_DIR.iterdir() if p.is_dir() and p.name not in before]
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _stage_hint(run_folder: Path | None) -> str:
    if run_folder is None or not run_folder.exists():
        return "starting"
    if (run_folder / "output" / "article.md").exists():
        return "finalizing"
    visuals = run_folder / "visuals"
    if visuals.exists() and any(visuals.iterdir()):
        return "adding visuals"
    audit = run_folder / "audit"
    if audit.exists() and any(audit.iterdir()):
        return "auditing / repairing"
    draft = run_folder / "draft"
    if draft.exists() and any(draft.iterdir()):
        return "writing"
    if (run_folder / "outline" / "outline.json").exists():
        return "outline ready"
    evidence = run_folder / "evidence"
    if evidence.exists() and any(evidence.iterdir()):
        return "researching"
    if (run_folder / "topic.txt").exists():
        return "planning"
    return "starting"


# ---------------------------------------------------------------------------
# Driving the `claude` CLI in headless mode
# ---------------------------------------------------------------------------

def _run_claude(prompt: str, resume: str | None, timeout_s: int = DEFAULT_TIMEOUT_S) -> dict:
    cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "json"]
    if resume:
        cmd += ["--resume", resume]
    try:
        proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True,
                              text=True, timeout=timeout_s)
    except FileNotFoundError:
        return {"ok": False, "error": (
            "`claude` was not found on PATH by this server process. Make sure "
            "Claude Code is installed and that running `claude --version` works "
            "in the same terminal you launched ui/server.py from.")}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": (
            f"claude did not finish within {timeout_s}s. It may still be running -- "
            "check with `claude --resume <session_id>` directly (see the debug panel "
            "for the session id if one was captured).")}

    raw_stdout = proc.stdout.strip()
    raw_stderr = proc.stderr.strip()

    if proc.returncode != 0 and not raw_stdout:
        hint = ""
        low = raw_stderr.lower()
        if "permission" in low or "trust" in low:
            hint = (" This looks like a permissions/trust issue -- make sure you've run "
                   "`claude` interactively in this folder at least once since "
                   ".claude/settings.json was added, and accepted the folder-trust "
                   "prompt if one appeared.")
        return {"ok": False, "error": f"claude exited with code {proc.returncode}.{hint}",
               "stderr": raw_stderr[-4000:]}

    try:
        data = json.loads(raw_stdout)
    except json.JSONDecodeError:
        # Not JSON -- surface the raw text rather than silently failing. This can
        # happen if claude prints a warning ahead of the JSON payload on some
        # versions; treat the whole thing as the message so nothing is lost.
        return {"ok": True, "session_id": resume, "result": raw_stdout,
               "raw_stdout": raw_stdout, "stderr": raw_stderr[-4000:]}

    data.setdefault("session_id", resume)
    data["ok"] = True
    data["raw_stdout"] = raw_stdout
    data["stderr"] = raw_stderr[-4000:]
    return data


def _background(run_id: str, fn, *args) -> None:
    def worker():
        try:
            fn(*args)
        except Exception as exc:  # noqa: BLE001 -- never let a bug here strand the UI silently
            with RUNS_LOCK:
                if run_id in RUNS:
                    RUNS[run_id]["status"] = "error"
                    RUNS[run_id]["error"] = f"{type(exc).__name__}: {exc}"
                    RUNS[run_id]["traceback"] = traceback.format_exc()
    threading.Thread(target=worker, daemon=True).start()


def _poll_stage_until_not_running(run_id: str, before: set[str] | None = None):
    """Cosmetic progress updates while a background `claude -p` call blocks."""
    def loop():
        while True:
            with RUNS_LOCK:
                run = RUNS.get(run_id)
                if run is None or run["status"] != "running":
                    return
                folder = run.get("run_folder")
            if folder is None and before is not None:
                found = _find_new_run_dir(before)
                if found is not None:
                    with RUNS_LOCK:
                        RUNS[run_id]["run_folder"] = str(found)
            with RUNS_LOCK:
                folder = RUNS[run_id].get("run_folder")
                RUNS[run_id]["stage"] = _stage_hint(Path(folder) if folder else None)
            time.sleep(2)
    threading.Thread(target=loop, daemon=True).start()


def _do_start(run_id: str, topic: str, newsletter: bool) -> None:
    before = _snapshot_run_dirs()
    with RUNS_LOCK:
        RUNS[run_id]["status"] = "running"
        RUNS[run_id]["stage"] = "starting"
    _poll_stage_until_not_running(run_id, before=before)

    prompt = f"/run-research {'--newsletter ' if newsletter else ''}{topic}".strip()
    result = _run_claude(prompt, resume=None)

    with RUNS_LOCK:
        run = RUNS[run_id]
        run["last_raw"] = result
        if not result.get("ok"):
            run["status"] = "error"
            run["error"] = result.get("error", "Unknown error running claude.")
            return
        run["session_id"] = result.get("session_id")
        run["last_message"] = result.get("result", "")
        folder = run.get("run_folder")
        if folder is None:
            found = _find_new_run_dir(before)
            if found is not None:
                folder = str(found)
                run["run_folder"] = folder
        outline = None
        done = False
        if folder:
            outline_path = Path(folder) / "outline" / "outline.json"
            article_path = Path(folder) / "output" / "article.md"
            if outline_path.exists():
                try:
                    outline = json.loads(outline_path.read_text(encoding="utf-8"))
                except Exception:
                    outline = None
            if article_path.exists():
                run["article_md"] = article_path.read_text(encoding="utf-8")
                done = True
        run["outline"] = outline
        run["status"] = "done" if done else "awaiting_decision"


def _do_decision(run_id: str, action: str, feedback: str) -> None:
    with RUNS_LOCK:
        run = RUNS[run_id]
        session_id = run.get("session_id")
        folder = run.get("run_folder")
        run["status"] = "running"
        run["stage"] = "generating" if action == "approve" else "revising outline"

    _poll_stage_until_not_running(run_id)

    if action == "approve":
        message = ("Approved -- proceed exactly with the outline as last shown to me. "
                   "Write the full report now and continue through the rest of the "
                   "/run-research pipeline (audit, repair, visuals, publish) without "
                   "stopping again.")
    else:
        message = feedback.strip() or "Please revise the outline."

    result = _run_claude(message, resume=session_id)

    with RUNS_LOCK:
        run = RUNS[run_id]
        run["last_raw"] = result
        if not result.get("ok"):
            run["status"] = "error"
            run["error"] = result.get("error", "Unknown error running claude.")
            return
        run["last_message"] = result.get("result", "")
        if folder:
            article_path = Path(folder) / "output" / "article.md"
            outline_path = Path(folder) / "outline" / "outline.json"
            if article_path.exists():
                run["article_md"] = article_path.read_text(encoding="utf-8")
                run["status"] = "done"
                return
            if outline_path.exists():
                try:
                    run["outline"] = json.loads(outline_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
        run["status"] = "awaiting_decision"


# ---------------------------------------------------------------------------
# Minimal, dependency-free PDF writer -- for the dashboard's "Download PDF"
# button. This is NOT a general-purpose PDF library: it lays out plain-text
# blocks (headings, paragraphs, bullets, blockquotes) onto Letter-sized
# pages using the PDF standard-14 fonts (Helvetica family), which every PDF
# reader renders natively with zero font embedding. Kept dependency-free on
# purpose, consistent with the rest of this edition (no pip install, ever).
#
# Deliberate limitation: it does not embed the report's figures -- each
# figure becomes a bracketed placeholder line instead, since embedding SVG
# into a hand-written PDF would require a vector-graphics translator well
# beyond what a "no dependencies" text layout engine can reasonably do. The
# on-screen dashboard view (which fetches real images via /api/asset/) and
# research_runs/<run>/output/article.md remain the full-fidelity versions.
# ---------------------------------------------------------------------------

_PDF_PAGE_W = 612.0   # Letter, points
_PDF_PAGE_H = 792.0
_PDF_MARGIN = 56.0
_PDF_CONTENT_W = _PDF_PAGE_W - 2 * _PDF_MARGIN

# (PDF resource name, average-glyph-width-as-fraction-of-size). The width
# ratio is only used to decide *where* to wrap lines -- actual on-page
# rendering uses the real Helvetica metrics built into every PDF reader.
# Deliberately a little generous (wider than Helvetica's true average) so
# wrapped lines land safely inside the margin rather than risk overrunning
# it.
_PDF_FONTS = {
    "regular": ("FHR", 0.52),
    "bold": ("FHB", 0.56),
    "italic": ("FHI", 0.52),
}

_UNICODE_TO_ASCII = {
    "—": "--", "–": "-", "‘": "'", "’": "'",
    "“": '"', "”": '"', "…": "...", "→": "->",
    "•": "-", " ": " ",
}


def _pdf_escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _pdf_normalize(text: str) -> str:
    for k, v in _UNICODE_TO_ASCII.items():
        text = text.replace(k, v)
    return text


def _clean_inline(text: str) -> str:
    text = _pdf_normalize(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip()


def _wrap_text(text: str, font_key: str, size: float, max_width: float) -> list[str]:
    _, ratio = _PDF_FONTS[font_key]
    avg_char_w = max(size * ratio, 1.0)
    max_chars = max(1, int(max_width / avg_char_w))
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    cur = ""
    for w in words:
        candidate = (cur + " " + w).strip()
        if len(candidate) <= max_chars or not cur:
            cur = candidate
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def markdown_to_pdf_blocks(md: str) -> list[dict]:
    """Parse the delimited-article-format markdown (see render_markdown.py)
    into simple block dicts a PDF layout pass can consume. Deliberately
    covers only what render_markdown.py actually emits -- headings,
    paragraphs, bullet/numbered lists, blockquotes, image lines (become a
    text placeholder), and single-asterisk-wrapped caption/meta lines."""
    blocks: list[dict] = []
    para_buf: list[str] = []

    def flush_para():
        if para_buf:
            text = _clean_inline(" ".join(l.strip() for l in para_buf if l.strip()))
            if text:
                blocks.append({"type": "p", "text": text})
            para_buf.clear()

    for raw in (md or "").split("\n"):
        stripped = raw.strip()
        if not stripped:
            flush_para()
            continue
        m_img = re.match(r"^!\[([^\]]*)\]\(([^)]*)\)$", stripped)
        m_num = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if stripped.startswith("### "):
            flush_para(); blocks.append({"type": "h3", "text": _clean_inline(stripped[4:])})
        elif stripped.startswith("## "):
            flush_para(); blocks.append({"type": "h2", "text": _clean_inline(stripped[3:])})
        elif stripped.startswith("# "):
            flush_para(); blocks.append({"type": "h1", "text": _clean_inline(stripped[2:])})
        elif stripped.startswith("> "):
            flush_para(); blocks.append({"type": "quote", "text": _clean_inline(stripped[2:])})
        elif m_img:
            flush_para()
            alt = m_img.group(1) or "figure"
            blocks.append({"type": "figure", "text": f"[Figure: {_pdf_normalize(alt)} "
                                                      "-- see the dashboard or article.md for the image]"})
        elif stripped.startswith("- ") or stripped.startswith("* "):
            flush_para(); blocks.append({"type": "bullet", "text": _clean_inline(stripped[2:])})
        elif m_num:
            flush_para()
            blocks.append({"type": "numbered", "n": int(m_num.group(1)), "text": _clean_inline(m_num.group(2))})
        elif re.match(r"^-{3,}$|^\*{3,}$", stripped):
            flush_para(); blocks.append({"type": "hr", "text": ""})
        elif stripped.startswith("*") and stripped.endswith("*") and not stripped.startswith("**") and len(stripped) > 2:
            flush_para(); blocks.append({"type": "meta", "text": _clean_inline(stripped[1:-1])})
        else:
            para_buf.append(stripped)
    flush_para()
    return blocks


def _layout_pdf_pages(blocks: list[dict]) -> list[list[tuple]]:
    """Turn blocks into pages of (x, y, font_resource_name, size, text)
    absolute-position draw commands, breaking to a new page whenever the
    next line would fall below the bottom margin."""
    pages: list[list[tuple]] = []
    current: list[tuple] = []
    y = [_PDF_PAGE_H - _PDF_MARGIN]

    def new_page():
        nonlocal current
        if current:
            pages.append(current)
        current = []
        y[0] = _PDF_PAGE_H - _PDF_MARGIN

    def emit(text: str, font_key: str, size: float, indent: float = 0.0, gap_after: float = 0.0):
        line_height = size * 1.35
        if y[0] - line_height < _PDF_MARGIN:
            new_page()
        font_res = _PDF_FONTS[font_key][0]
        current.append((_PDF_MARGIN + indent, y[0], font_res, size, text))
        y[0] -= line_height + gap_after

    for b in blocks:
        t = b["type"]
        if t == "h1":
            for ln in _wrap_text(b["text"], "bold", 20, _PDF_CONTENT_W):
                emit(ln, "bold", 20)
            y[0] -= 6
        elif t == "h2":
            y[0] -= 6
            for ln in _wrap_text(b["text"], "bold", 14, _PDF_CONTENT_W):
                emit(ln, "bold", 14)
            y[0] -= 4
        elif t == "h3":
            for ln in _wrap_text(b["text"], "bold", 12, _PDF_CONTENT_W):
                emit(ln, "bold", 12)
        elif t == "quote":
            for ln in _wrap_text(b["text"], "italic", 11, _PDF_CONTENT_W - 24):
                emit(ln, "italic", 11, indent=24)
            y[0] -= 4
        elif t == "bullet":
            wrapped = _wrap_text(b["text"], "regular", 11, _PDF_CONTENT_W - 16)
            for i, ln in enumerate(wrapped):
                emit(("-  " if i == 0 else "   ") + ln, "regular", 11, indent=10)
        elif t == "numbered":
            wrapped = _wrap_text(b["text"], "regular", 11, _PDF_CONTENT_W - 20)
            for i, ln in enumerate(wrapped):
                prefix = f"{b['n']}. " if i == 0 else "    "
                emit(prefix + ln, "regular", 11, indent=10)
        elif t == "figure":
            for ln in _wrap_text(b["text"], "italic", 9.5, _PDF_CONTENT_W):
                emit(ln, "italic", 9.5)
            y[0] -= 4
        elif t == "meta":
            for ln in _wrap_text(b["text"], "italic", 10, _PDF_CONTENT_W):
                emit(ln, "italic", 10)
            y[0] -= 6
        elif t == "hr":
            y[0] -= 10
        else:  # plain paragraph
            for ln in _wrap_text(b["text"], "regular", 11, _PDF_CONTENT_W):
                emit(ln, "regular", 11)
            y[0] -= 6
    new_page()
    return pages


def _pdf_content_stream(lines: list[tuple]) -> bytes:
    parts = []
    for x, y, font_res, size, text in lines:
        parts.append(f"BT /{font_res} {size:.1f} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm ({_pdf_escape(text)}) Tj ET")
    return "\n".join(parts).encode("latin-1", "replace")


def build_pdf_bytes(pages_lines: list[list[tuple]]) -> bytes:
    if not pages_lines:
        pages_lines = [[]]
    n_pages = len(pages_lines)
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique >>",
    }
    page_nums, content_nums = [], []
    next_num = 6
    for _ in range(n_pages):
        page_nums.append(next_num); next_num += 1
        content_nums.append(next_num); next_num += 1
    kids = " ".join(f"{n} 0 R" for n in page_nums)
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode()
    for i, lines in enumerate(pages_lines):
        page_num, content_num = page_nums[i], content_nums[i]
        objects[page_num] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_PDF_PAGE_W} {_PDF_PAGE_H}] "
            f"/Resources << /Font << /FHR 3 0 R /FHB 4 0 R /FHI 5 0 R >> >> "
            f"/Contents {content_num} 0 R >>"
        ).encode()
        stream_body = _pdf_content_stream(lines)
        objects[content_num] = (f"<< /Length {len(stream_body)} >>\nstream\n".encode()
                                + stream_body + b"\nendstream")

    out = bytearray()
    out += b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    max_num = max(objects.keys())
    offsets: dict[int, int] = {}
    for num in range(1, max_num + 1):
        offsets[num] = len(out)
        body = objects.get(num, b"<< >>")
        out += f"{num} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_offset = len(out)
    out += f"xref\n0 {max_num + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for num in range(1, max_num + 1):
        out += f"{offsets[num]:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {max_num + 1} /Root 1 0 R >>\n"
           f"startxref\n{xref_offset}\n%%EOF").encode()
    return bytes(out)


def markdown_to_pdf_bytes(md: str) -> bytes:
    return build_pdf_bytes(_layout_pdf_pages(markdown_to_pdf_blocks(md)))


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SEARCH AI -- Research Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
  /* ============================================================
     SEARCH AI -- neumorphic interface (matches the API Edition's
     porcelain-base, dual-soft-shadow, indigo-accent look).
     ============================================================ */
  :root {
    color-scheme: light;
    --base:#E7EBF4; --base-deep:#DDE2EF;
    --ink:#242B47; --ink-soft:#6E7796;
    --accent:#4F6BF0; --accent-deep:#3A53CF; --accent-warm:#E8734A;
    --good:#2FA98C; --warn:#D99A2B; --bad:#D9534F;
    --hi:rgba(255,255,255,.92); --lo:rgba(105,118,160,.38);
    --radius:22px;
    --font-display:'Sora',sans-serif; --font-body:'Inter',sans-serif;
    --font-mono:'JetBrains Mono',monospace;
  }
  * { box-sizing: border-box; }
  html { scroll-behavior: smooth; }
  body {
    font-family: var(--font-body); max-width: 880px; margin: 0 auto;
    padding: 40px 20px 80px; line-height: 1.55; color: var(--ink);
    background: var(--base);
    background-image: radial-gradient(1200px 500px at 50% -10%, #F2F5FC 0%, var(--base) 60%);
    -webkit-font-smoothing: antialiased;
  }
  h1 {
    font-family: var(--font-display); font-size: 1.7rem; font-weight: 800;
    letter-spacing: .01em; margin-bottom: 4px; color: var(--ink);
  }
  h1 span { color: var(--accent); }
  .sub { color: var(--ink-soft); font-size: 0.9rem; margin-bottom: 26px; max-width: 640px; }
  .sub code {
    font: 500 .85em var(--font-mono); background: var(--base-deep);
    color: var(--accent-deep); border-radius: 5px; padding: 1px 6px;
  }
  .card {
    background: var(--base); border-radius: var(--radius);
    box-shadow: -9px -9px 20px var(--hi), 9px 9px 22px var(--lo);
    padding: 22px 24px; margin-bottom: 20px;
  }
  textarea, input[type=text] {
    width: 100%; font: inherit; color: var(--ink); padding: 11px 13px;
    border: none; outline: none; border-radius: 14px; resize: vertical;
    background: var(--base-deep);
    box-shadow: inset 4px 4px 9px var(--lo), inset -4px -4px 9px var(--hi);
  }
  textarea::placeholder { color: #98A0BC; }
  label { font-family: var(--font-display); font-weight: 600; font-size: .95rem; }
  label.chk {
    display: flex; align-items: center; gap: 9px; font: 500 .88rem var(--font-body);
    color: var(--ink-soft); margin: 14px 0 4px;
  }
  label.chk input[type=checkbox] { width: 16px; height: 16px; accent-color: var(--accent); }
  button {
    font: 600 .88rem var(--font-body); padding: 11px 20px; border-radius: 14px;
    border: none; cursor: pointer; color: var(--ink); background: var(--base);
    box-shadow: -6px -6px 13px var(--hi), 6px 6px 14px var(--lo);
    transition: transform .12s ease, box-shadow .15s ease, opacity .15s;
  }
  button:hover:not(:disabled) { transform: translateY(-1px); }
  button:active:not(:disabled) {
    box-shadow: inset 4px 4px 9px var(--lo), inset -4px -4px 9px var(--hi);
    transform: translateY(0);
  }
  button:disabled { opacity: 0.45; cursor: default; }
  button + button { margin-left: 10px; }
  #start-btn, button#start-btn {
    font-size: 1rem; padding: 13px 28px; color: #fff;
    background: linear-gradient(145deg,#5B76F4,#4257D8);
    box-shadow: -6px -6px 13px var(--hi), 6px 6px 15px rgba(63,83,200,.45);
    margin-top: 14px;
  }
  button.secondary { color: var(--ink-soft); }
  button.danger {
    color: #fff; background: linear-gradient(145deg,#E2695F,#C7473D);
    box-shadow: -6px -6px 13px var(--hi), 6px 6px 15px rgba(199,71,61,.4);
  }
  .stage {
    display: inline-flex; align-items: center; gap: 9px; font-weight: 700;
    font-family: var(--font-display); font-size: .98rem;
  }
  .dot {
    width: 10px; height: 10px; border-radius: 50%; background: var(--accent);
    box-shadow: 0 0 0 4px rgba(79,107,240,.18);
    animation: pulse-dot 1.1s ease infinite;
  }
  @keyframes pulse-dot {
    0%,100% { box-shadow: 0 0 0 4px rgba(79,107,240,.18); }
    50% { box-shadow: 0 0 0 7px rgba(79,107,240,.08); }
  }
  .section-item {
    padding: 14px 16px; border-radius: 16px; background: var(--base);
    box-shadow: -5px -5px 12px var(--hi), 5px 5px 13px var(--lo);
    margin-top: 12px;
  }
  .section-item:first-child { margin-top: 0; }
  .section-item .title { font-family: var(--font-display); font-weight: 700; color: var(--ink); }
  .section-item .goal { color: var(--ink-soft); font-size: 0.88rem; margin-top: 3px; font-style: italic; }
  pre.article {
    white-space: pre-wrap; word-wrap: break-word; max-height: 60vh; overflow: auto;
    background: var(--base-deep); border-radius: 16px; padding: 16px 18px;
    box-shadow: inset 4px 4px 9px var(--lo), inset -4px -4px 9px var(--hi);
    font-size: 0.86rem; font-family: var(--font-mono);
  }
  .article-view {
    max-height: 70vh; overflow: auto; background: #FDFDFF; border-radius: 18px;
    padding: 26px 30px; margin-top: 14px;
    box-shadow: -6px -6px 14px var(--hi), 6px 6px 16px var(--lo);
  }
  .article-view h1 {
    font-size: 1.55rem; margin: 4px 0 10px; font-family: var(--font-display); color: var(--ink);
  }
  .article-view h2 {
    font-size: 1.18rem; margin: 26px 0 10px; font-family: var(--font-display); color: var(--ink);
  }
  .article-view h3 { font-size: 1.02rem; margin: 16px 0 7px; font-family: var(--font-display); }
  .article-view p { margin: 0 0 12px; font-size: 0.96rem; color: #2A3049; }
  .article-view ul, .article-view ol { margin: 0 0 12px; padding-left: 24px; font-size: 0.96rem; }
  .article-view li { margin: 4px 0; }
  .article-view a { color: var(--accent-deep); }
  .article-view code {
    font: 500 .86em var(--font-mono); background: #EEF1FA; color: #3A4470;
    border-radius: 6px; padding: 2px 6px;
  }
  .article-view blockquote {
    margin: 16px 0; padding: 16px 20px; border-radius: 16px; background: var(--base);
    box-shadow: -5px -5px 12px var(--hi), 5px 5px 13px var(--lo);
    font-family: var(--font-display); font-weight: 600; color: var(--accent-deep);
    font-style: normal; font-size: 0.98rem;
  }
  .article-view img {
    max-width: 100%; border-radius: 14px; margin: 10px 0; display: block;
    box-shadow: 0 6px 22px rgba(70,85,140,.22);
  }
  .article-view figcaption, .article-view .fig-caption {
    font-size: 0.8rem; color: var(--ink-soft); font-style: italic; margin: -4px 0 14px;
  }
  .article-view hr { border: none; border-top: 1px solid rgba(110,119,150,.22); margin: 20px 0; }
  .article-view .meta-line { color: var(--ink-soft); font-size: 0.85rem; margin: -4px 0 16px; }
  .muted { color: var(--ink-soft); font-size: 0.85rem; }
  .error-box {
    background: #FBEAE8; color: #8a2b22; border-left: 5px solid var(--bad);
    border-radius: 0 14px 14px 0; padding: 14px 18px; font-size: 0.92rem;
  }
  details summary {
    cursor: pointer; font: 600 .82rem var(--font-body); color: var(--ink-soft); margin-top: 12px;
  }
  details pre {
    font-family: var(--font-mono); font-size: 0.78rem; max-height: 240px; overflow: auto;
    background: #232842; color: #E7EBFA; padding: 14px 16px; border-radius: 12px; margin-top: 8px;
    box-shadow: inset 0 2px 12px rgba(0,0,0,.35);
  }
  .history-item {
    padding: 10px 12px; border-radius: 12px; cursor: pointer; font-size: 0.9rem;
    color: var(--ink); margin-top: 6px; transition: box-shadow .15s ease;
  }
  .history-item:first-child { margin-top: 10px; }
  .history-item:hover {
    color: var(--accent-deep);
    box-shadow: inset 3px 3px 7px var(--lo), inset -3px -3px 7px var(--hi);
  }
  .badge {
    font: 700 .68rem var(--font-mono); text-transform: uppercase; letter-spacing: 0.06em;
    padding: 4px 10px; border-radius: 999px; background: rgba(79,107,240,.12);
    color: var(--accent-deep);
  }
  .card > strong, .card > label > strong {
    font-family: var(--font-display); font-weight: 700; font-size: 1rem; color: var(--ink);
  }
</style>
</head>
<body>
  <h1>SEARCH <span>AI</span> -- Research Dashboard</h1>
  <div class="sub">Claude Code Edition, driven from a browser tab. This is a convenience
    layer around <code>/run-research</code> -- everything it does, /run-research also does
    typed directly into Claude Code. If anything here seems stuck, that terminal is always
    the fallback.</div>

  <div class="card" id="new-run-card">
    <label for="topic"><strong>Research topic</strong></label>
    <textarea id="topic" rows="2" placeholder="e.g. North Star Metric frameworks for B2B SaaS"></textarea>
    <label class="chk"><input type="checkbox" id="newsletter"> Newsletter format (curated-links
      digest instead of a single deep-dive report)</label>
    <button id="start-btn" onclick="startRun()">START</button>
    <div class="muted" id="start-hint" style="margin-top:8px;"></div>
  </div>

  <div class="card" id="active-card" style="display:none;"></div>

  <div class="card" id="history-card">
    <strong>Past runs this session</strong>
    <div id="history-list" class="muted">None yet.</div>
  </div>

<script>
let currentRunId = null;
let pollTimer = null;

async function startRun() {
  const topic = document.getElementById('topic').value.trim();
  if (!topic) { document.getElementById('start-hint').textContent = 'Type a topic first.'; return; }
  document.getElementById('start-btn').disabled = true;
  document.getElementById('start-hint').textContent = 'Starting...';
  const newsletter = document.getElementById('newsletter').checked;
  const res = await fetch('/api/start', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({topic, newsletter})
  });
  const data = await res.json();
  document.getElementById('start-btn').disabled = false;
  document.getElementById('start-hint').textContent = '';
  if (data.error) { alert(data.error); return; }
  currentRunId = data.run_id;
  document.getElementById('topic').value = '';
  poll();
  loadHistory();
}

function selectRun(id) {
  currentRunId = id;
  poll();
}

async function decide(action) {
  let feedback = '';
  if (action === 'regenerate') {
    feedback = prompt('What should change about the outline?') || '';
    if (!feedback) return;
  }
  if (action === 'discard' && !confirm('Discard this run? This just stops the dashboard from tracking it.')) return;
  await fetch(`/api/decision/${currentRunId}`, {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({action, feedback})
  });
  poll();
}

async function sendReply() {
  const box = document.getElementById('reply-box');
  const feedback = (box && box.value || '').trim();
  if (!feedback) return;
  // Reuses the same server-side path as outline feedback -- it just
  // forwards whatever text you type as the next turn via `claude --resume`.
  // That's exactly right here too: answering "ROC = the ML curve" is the
  // same kind of message as "make section 2 shorter".
  await fetch(`/api/decision/${currentRunId}`, {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({action: 'regenerate', feedback})
  });
  poll();
}

function escapeHtml(s) {
  return (s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

async function poll() {
  if (pollTimer) clearTimeout(pollTimer);
  if (!currentRunId) return;
  const res = await fetch(`/api/status/${currentRunId}`);
  if (!res.ok) return;
  const run = await res.json();
  render(run);
  if (run.status === 'running' || run.status === 'starting') {
    pollTimer = setTimeout(poll, 2000);
  }
}

function render(run) {
  const card = document.getElementById('active-card');
  card.style.display = 'block';
  let html = `<div><span class="badge">${escapeHtml(run.status)}</span> &nbsp;<strong>${escapeHtml(run.topic)}</strong>${run.newsletter ? ' <span class="badge">newsletter</span>' : ''}</div>`;

  if (run.status === 'starting' || run.status === 'running') {
    html += `<p class="stage"><span class="dot"></span> ${escapeHtml(run.stage || 'working')}...</p>`;
    html += `<p class="muted">This can take a few minutes, especially while real web sources are being gathered. Feel free to leave this tab open and come back.</p>`;
  } else if (run.status === 'awaiting_decision' && run.outline) {
    html += `<p><strong>Outline ready for review.</strong> Nothing is written in full until you approve it.</p>`;
    html += `<p class="muted">Layout: ${escapeHtml(run.outline.layout || 'auto')}${run.outline.narrative_thread ? ' -- ' + escapeHtml(run.outline.narrative_thread) : ''}</p>`;
    (run.outline.sections || []).forEach(s => {
      html += `<div class="section-item"><div class="title">${escapeHtml(s.title || '')}</div><div class="goal">${escapeHtml(s.goal || '')}</div></div>`;
    });
    html += `<div style="margin-top:14px;">
      <button onclick="decide('approve')">Approve &amp; Write Full Report</button>
      <button class="secondary" onclick="decide('regenerate')">Regenerate with Feedback</button>
      <button class="danger" onclick="decide('discard')">Discard</button>
    </div>`;
  } else if (run.status === 'awaiting_decision' && !run.outline) {
    // No outline.json exists yet -- this is NOT "outline ready", it means
    // /run-research ended its turn some other way, most commonly by asking
    // a clarifying question (ambiguous topic, missing detail) rather than
    // researching anything. Offering "Approve" here would be actively
    // misleading -- there is nothing to approve yet.
    html += `<p><strong>Claude needs more information before it can build an outline:</strong></p>`;
    html += `<pre class="article">${escapeHtml(run.last_message || '(no message captured -- see debug panel)')}</pre>`;
    html += `<textarea id="reply-box" rows="2" placeholder="Type your answer here..." style="margin-top:8px;"></textarea>`;
    html += `<div style="margin-top:10px;">
      <button onclick="sendReply()">Send Reply</button>
      <button class="danger" onclick="decide('discard')">Discard</button>
    </div>`;
  } else if (run.status === 'done') {
    html += `<p><strong>Done.</strong> Report shown below -- press PDF to download it.</p>`;
    html += `<button onclick="downloadPdf('${run.id}')">Download PDF</button>`;
    html += `<div class="article-view">${mdToHtml(run.article_md || run.last_message || '', run.id)}</div>`;
  } else if (run.status === 'error') {
    html += `<div class="error-box"><strong>Something went wrong:</strong> ${escapeHtml(run.error || 'unknown error')}</div>`;
  } else if (run.status === 'discarded') {
    html += `<p class="muted">Discarded.</p>`;
  }

  if (run.session_id) {
    html += `<details><summary>Debug info</summary><pre>session_id: ${escapeHtml(run.session_id)}
run_folder: ${escapeHtml(run.run_folder || '(not found yet)')}

To continue this exact conversation by hand in the terminal instead:
  claude --resume ${escapeHtml(run.session_id)}

stderr (tail):
${escapeHtml((run.debug && run.debug.stderr_tail) || '(none)')}</pre></details>`;
  }

  card.innerHTML = html;
  window._lastRun = run;
}

function downloadPdf(id) {
  // Navigating to the endpoint (rather than fetching a Blob) lets the
  // browser handle the download natively via the server's
  // Content-Disposition header -- no client-side PDF library needed.
  window.location.href = `/api/pdf/${id}`;
}

function mdInline(text, runId) {
  let s = escapeHtml(text);
  s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/\*(.+?)\*/g, '<em>$1</em>');
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  return s;
}

// Renders the exact markdown shape scripts/render_markdown.py produces
// (headings, paragraphs, bullet/numbered lists, blockquotes, image lines,
// a single horizontal rule, and single-asterisk meta/caption lines) as
// on-screen HTML. This is intentionally tailored to that known shape, not
// a general markdown parser. Images are rewritten to fetch through
// /api/asset/<runId>/<path> since the raw report references files on disk
// relative to the run folder, which the browser can't reach directly.
function mdToHtml(md, runId) {
  const lines = (md || '').split('\\n');
  let html = '';
  let para = [];
  let listType = null; // 'ul' | 'ol' | null

  function flushPara() {
    if (para.length) {
      html += `<p>${mdInline(para.join(' '), runId)}</p>`;
      para = [];
    }
  }
  function closeList() {
    if (listType) { html += `</${listType}>`; listType = null; }
  }

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) { flushPara(); continue; }
    const mImg = line.match(/^!\[([^\]]*)\]\(([^)]*)\)$/);
    const mNum = line.match(/^(\d+)\.\s+(.*)$/);
    if (line.startsWith('### ')) {
      flushPara(); closeList(); html += `<h3>${mdInline(line.slice(4), runId)}</h3>`;
    } else if (line.startsWith('## ')) {
      flushPara(); closeList(); html += `<h2>${mdInline(line.slice(3), runId)}</h2>`;
    } else if (line.startsWith('# ')) {
      flushPara(); closeList(); html += `<h1>${mdInline(line.slice(2), runId)}</h1>`;
    } else if (line.startsWith('> ')) {
      flushPara(); closeList(); html += `<blockquote>${mdInline(line.slice(2), runId)}</blockquote>`;
    } else if (mImg) {
      flushPara(); closeList();
      const alt = mImg[1] || 'figure';
      const src = `/api/asset/${runId}/${mImg[2].split('/').map(encodeURIComponent).join('/')}`;
      html += `<img src="${src}" alt="${escapeHtml(alt)}" loading="lazy">`;
    } else if (line.startsWith('- ') || line.startsWith('* ')) {
      flushPara();
      if (listType !== 'ul') { closeList(); html += '<ul>'; listType = 'ul'; }
      html += `<li>${mdInline(line.slice(2), runId)}</li>`;
    } else if (mNum) {
      flushPara();
      if (listType !== 'ol') { closeList(); html += '<ol>'; listType = 'ol'; }
      html += `<li>${mdInline(mNum[2], runId)}</li>`;
    } else if (/^-{3,}$|^\*{3,}$/.test(line)) {
      flushPara(); closeList(); html += '<hr>';
    } else if (line.startsWith('*') && line.endsWith('*') && !line.startsWith('**') && line.length > 2) {
      flushPara(); closeList();
      html += `<div class="meta-line fig-caption">${mdInline(line.slice(1, -1), runId)}</div>`;
    } else {
      closeList();
      para.push(line);
    }
  }
  flushPara(); closeList();
  return html || '<p class="muted">(empty report)</p>';
}

async function loadHistory() {
  const res = await fetch('/api/runs');
  const data = await res.json();
  const el = document.getElementById('history-list');
  if (!data.runs || !data.runs.length) { el.textContent = 'None yet.'; return; }
  el.innerHTML = data.runs.map(r =>
    `<div class="history-item" onclick="selectRun('${r.id}')">
       <span class="badge">${escapeHtml(r.status)}</span> ${escapeHtml(r.topic)}
     </div>`).join('');
}

loadHistory();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "SearchAIDashboard/1.0"

    def _send_json(self, obj, status: int = 200) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, status: int = 200) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def log_message(self, fmt, *args) -> None:  # noqa: D401 -- keep the terminal quiet
        pass

    def do_GET(self) -> None:  # noqa: N802 -- BaseHTTPRequestHandler API
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send_html(INDEX_HTML)
            return
        if path == "/api/runs":
            with RUNS_LOCK:
                items = [{"id": r["id"], "topic": r["topic"], "newsletter": r["newsletter"],
                         "status": r["status"], "created": r["created"]} for r in RUNS.values()]
            items.sort(key=lambda x: x["created"], reverse=True)
            self._send_json({"runs": items})
            return
        m = re.match(r"^/api/status/([a-f0-9]+)$", path)
        if m:
            run_id = m.group(1)
            with RUNS_LOCK:
                run = RUNS.get(run_id)
                if run is None:
                    self._send_json({"error": "unknown run_id"}, status=404)
                    return
                snapshot = dict(run)
            last_raw = snapshot.pop("last_raw", None) or {}
            snapshot["debug"] = {
                "stderr_tail": (last_raw.get("stderr") or "")[-2000:],
            }
            self._send_json(snapshot)
            return
        m = re.match(r"^/api/pdf/([a-f0-9]+)$", path)
        if m:
            run_id = m.group(1)
            with RUNS_LOCK:
                run = RUNS.get(run_id)
                article_md = run.get("article_md") if run else None
                topic = (run or {}).get("topic", "article")
            if run is None:
                self._send_json({"error": "unknown run_id"}, status=404)
                return
            if not article_md:
                self._send_json({"error": "this run has no finished report yet"}, status=400)
                return
            try:
                pdf_bytes = markdown_to_pdf_bytes(article_md)
            except Exception as exc:  # pragma: no cover -- defensive, PDF writer is new
                self._send_json({"error": f"failed to build PDF: {exc}"}, status=500)
                return
            slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:60] or "article"
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(pdf_bytes)))
            self.send_header("Content-Disposition", f'attachment; filename="{slug}.pdf"')
            self.end_headers()
            self.wfile.write(pdf_bytes)
            return
        m = re.match(r"^/api/asset/([a-f0-9]+)/(.+)$", path)
        if m:
            run_id, rel_path = m.group(1), unquote(m.group(2))
            with RUNS_LOCK:
                run = RUNS.get(run_id)
                folder = run.get("run_folder") if run else None
            if run is None or not folder:
                self._send_json({"error": "unknown run_id or run has no folder yet"}, status=404)
                return
            base = Path(folder).resolve()
            candidate = (base / rel_path).resolve()
            if base not in candidate.parents and candidate != base:
                self._send_json({"error": "invalid path"}, status=400)
                return
            if not candidate.is_file():
                self._send_json({"error": "asset not found"}, status=404)
                return
            ctype = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
            data = candidate.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self._send_json({"error": "not found"}, status=404)

    def do_POST(self) -> None:  # noqa: N802 -- BaseHTTPRequestHandler API
        path = urlparse(self.path).path
        if path == "/api/start":
            body = self._read_json_body()
            topic = (body.get("topic") or "").strip()
            newsletter = bool(body.get("newsletter"))
            if not topic:
                self._send_json({"error": "topic is required"}, status=400)
                return
            run_id = uuid.uuid4().hex[:8]
            with RUNS_LOCK:
                RUNS[run_id] = {
                    "id": run_id, "topic": topic, "newsletter": newsletter,
                    "status": "starting", "stage": "starting", "created": time.time(),
                    "run_folder": None, "session_id": None, "outline": None,
                    "article_md": None, "last_message": "", "error": None,
                }
            _background(run_id, _do_start, run_id, topic, newsletter)
            self._send_json({"run_id": run_id})
            return
        m = re.match(r"^/api/decision/([a-f0-9]+)$", path)
        if m:
            run_id = m.group(1)
            with RUNS_LOCK:
                if run_id not in RUNS:
                    self._send_json({"error": "unknown run_id"}, status=404)
                    return
            body = self._read_json_body()
            action = body.get("action")
            feedback = body.get("feedback", "")
            if action not in ("approve", "regenerate", "discard"):
                self._send_json({"error": "action must be approve, regenerate, or discard"}, status=400)
                return
            if action == "discard":
                with RUNS_LOCK:
                    RUNS[run_id]["status"] = "discarded"
                self._send_json({"ok": True})
                return
            _background(run_id, _do_decision, run_id, action, feedback)
            self._send_json({"ok": True})
            return
        self._send_json({"error": "not found"}, status=404)


def main() -> None:
    port = 8787
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"SEARCH AI dashboard running at {url}")
    print("This drives the `claude` CLI in headless mode from this project folder.")
    print("Leave this window open while you use the dashboard. Press Ctrl+C to stop.")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
