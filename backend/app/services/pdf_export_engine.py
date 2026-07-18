"""PDF Export Engine — backend fallback only.

Primary PDF export is the frontend screenshot pipeline (html2canvas + jsPDF),
which reproduces the live article pixel-for-pixel. This backend engine exists
as a fallback for environments where the browser export is unavailable; it
renders the provided article HTML through WeasyPrint if installed.
"""
from __future__ import annotations

from typing import Optional


def available() -> bool:
    try:
        import weasyprint  # noqa: F401
        return True
    except Exception:
        return False


def render_pdf(html: str, title: str = "SEARCH AI Article") -> Optional[bytes]:
    if not available():
        return None
    from weasyprint import HTML  # type: ignore

    page_css = """
    <style>
      @page { size: A4; margin: 16mm 14mm; }
      body { font-family: 'Segoe UI', Arial, sans-serif; color: #22283f; }
      img { max-width: 100%; }
      table { border-collapse: collapse; width: 100%; }
      th, td { border: 1px solid #d8ddec; padding: 6px 9px; font-size: 11px; }
      pre { background: #f2f4fb; border-radius: 8px; padding: 10px;
            font-size: 10.5px; white-space: pre-wrap; }
      blockquote { border-left: 4px solid #4f6bf0; margin: 12px 0;
                   padding: 6px 14px; font-style: italic; }
    </style>"""
    doc = f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title>{page_css}</head><body>{html}</body></html>"
    return HTML(string=doc).write_pdf()
