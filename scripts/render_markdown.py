#!/usr/bin/env python3
"""Renders final_publisher.py's assembled article JSON into a clean,
standalone Markdown deliverable — the same content model as the API
edition's markdown export, adapted for this edition's local SVG figure
files (referenced by relative path rather than embedded as data URIs).

Usage:
  python3 render_markdown.py <article_final.json> <out.md> [--images-dir <dir>]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from _jsonio import read_json


def _figure_line(img: dict, out_dir: Path) -> str:
    cap = (img.get("caption") or "").strip()
    src = (img.get("source_label") or "").strip()
    label = f"*Figure {img.get('slot', '')}: {cap}*" if cap else f"*Figure {img.get('slot', '')}*"
    url = img.get("url", "")
    try:
        rel = Path(url).resolve().relative_to(out_dir.resolve().parent)
        ref = str(rel)
    except Exception:
        ref = url
    body = f"![{cap or 'figure'}]({ref})\n\n{label}" + (f" — {src}" if src else "")
    return body


def render_markdown(article: dict, out_path: Path) -> str:
    images = article.get("images", [])
    by_section: dict[str, list[dict]] = {}
    loose: list[dict] = []
    for img in images:
        (by_section.setdefault(img.get("section_id", ""), []) if img.get("section_id")
         else loose).append(img)

    lines: list[str] = []
    title = article.get("title") or "SEARCH AI Article"
    lines.append(f"# {title}")
    lines.append("")
    topic = article.get("topic", "")
    layout = (article.get("layout") or "").replace("_", " ")
    meta_bits = [b for b in [f"SEARCH AI · {layout}" if layout else "SEARCH AI",
                             f"Topic: {topic}" if topic else ""] if b]
    if meta_bits:
        lines.append("*" + "  ·  ".join(meta_bits) + "*")
        lines.append("")

    if (article.get("abstract") or "").strip():
        lines.append("## Abstract")
        lines.append("")
        lines.append(article["abstract"].strip())
        lines.append("")

    if (article.get("executive_answer") or "").strip():
        lines.append("## Direct Answer")
        lines.append("")
        lines.append(article["executive_answer"].strip())
        lines.append("")

    takeaways = article.get("key_takeaways") or []
    if takeaways:
        lines.append("## Key Takeaways")
        lines.append("")
        for kt in takeaways:
            lines.append(f"- {str(kt).strip()}")
        lines.append("")

    sections = article.get("sections", [])
    for si, sec in enumerate(sections):
        lines.append(f"## {sec.get('title', '')}")
        lines.append("")
        if sec.get("pull_quote"):
            lines.append(f"> {sec['pull_quote']}")
            lines.append("")
        body = (sec.get("markdown") or "").strip()
        if body:
            lines.append(body)
            lines.append("")
        for img in by_section.get(sec.get("id", ""), []):
            lines.append(_figure_line(img, out_path))
            lines.append("")
        if loose and si % 2 == 1:
            lines.append(_figure_line(loose.pop(0), out_path))
            lines.append("")
    for img in loose:
        lines.append(_figure_line(img, out_path))
        lines.append("")

    refs = article.get("references", [])
    if refs:
        lines.append("## References")
        lines.append("")
        for i, r in enumerate(refs, start=1):
            bits = [r.get("title", "") or r.get("url", "")]
            if r.get("year"):
                bits.append(f"({r['year']})")
            if r.get("doi"):
                bits.append(f"doi:{r['doi']}")
            if r.get("url"):
                bits.append(r["url"])
            lines.append(f"{i}. " + "  ·  ".join(str(b) for b in bits if b))
        lines.append("")

    text = "\n".join(lines)
    return re.sub(r"\n{4,}", "\n\n\n", text).strip() + "\n"


def main(argv: list[str]) -> None:
    if len(argv) < 3:
        print("Usage: python3 render_markdown.py <article_final.json> <out.md>", file=sys.stderr)
        sys.exit(1)
    article = read_json(argv[1])
    out_path = Path(argv[2])
    out_path.write_text(render_markdown(article, out_path), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv)
