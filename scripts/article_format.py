#!/usr/bin/env python3
"""Delimited-markdown article (de)serialisation — shared by the
research-writer and repair-editor agents, and by final_publisher.py. Never
JSON for prose: JSON-encoding long professional writing is exactly the kind
of "unnecessary AI-ism" the output-style rules forbid, and a delimited text
format is far cheaper and more reliable for a model to produce correctly.

Format written by the writer/repair agents into a plain .md-with-markers
file (article_draft.md):

=== TITLE ===
=== ABSTRACT ===
=== ANSWER ===
=== TAKEAWAYS ===
- one per line
=== SECTION: <id> | <title> ===
PULL QUOTE: optional single line
markdown body
(repeat SECTION per outline section, in order)

Usage:
  python3 article_format.py parse <draft.md> <out.json>
  python3 article_format.py serialize <article.json> <out.md>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from _jsonio import read_json, write_json, usage

_BLOCK = re.compile(
    r"^===\s*(TITLE|ABSTRACT|ANSWER|TAKEAWAYS|SECTION)"
    r"(?:\s*:\s*([^\n=]+?))?\s*===\s*$", re.MULTILINE)


def parse_article(text: str) -> dict:
    text = re.sub(r"^```[a-z]*\n|```$", "", text.replace("\r\n", "\n").strip())
    out = {"title": "", "abstract": "", "executive_answer": "",
           "key_takeaways": [], "sections": []}
    ms = list(_BLOCK.finditer(text))
    for i, m in enumerate(ms):
        kind, param = m.group(1).upper(), (m.group(2) or "").strip()
        body = text[m.end():ms[i + 1].start() if i + 1 < len(ms) else len(text)].strip()
        if kind == "TITLE":
            out["title"] = body.splitlines()[0].strip() if body else ""
        elif kind == "ABSTRACT":
            out["abstract"] = body
        elif kind == "ANSWER":
            out["executive_answer"] = body
        elif kind == "TAKEAWAYS":
            out["key_takeaways"] = [re.sub(r"^[-*]\s*", "", ln).strip()
                                    for ln in body.splitlines()
                                    if re.match(r"^\s*[-*]", ln)][:7]
        elif kind == "SECTION":
            sid, _, title = param.partition("|")
            pull, lines = None, body.splitlines()
            for j, ln in enumerate(lines):
                if not ln.strip():
                    continue
                if ln.strip().upper().startswith("PULL QUOTE:"):
                    pull = ln.split(":", 1)[1].strip()
                    lines = lines[:j] + lines[j + 1:]
                break
            out["sections"].append({"id": sid.strip(), "title": title.strip(),
                                    "markdown": "\n".join(lines).strip(),
                                    "pull_quote": pull})
    return out


def serialize_article(a: dict) -> str:
    parts = [f"=== TITLE ===\n{a.get('title','')}",
             f"=== ABSTRACT ===\n{a.get('abstract','')}",
             f"=== ANSWER ===\n{a.get('executive_answer','')}",
             "=== TAKEAWAYS ===\n" +
             "\n".join(f"- {k}" for k in a.get("key_takeaways", []))]
    for s in a.get("sections", []):
        pq = f"PULL QUOTE: {s['pull_quote']}\n" if s.get("pull_quote") else ""
        parts.append(f"=== SECTION: {s.get('id','')} | {s.get('title','')} "
                     f"===\n{pq}{s.get('markdown','')}")
    return "\n\n".join(parts)


def main(argv: list[str]) -> None:
    if len(argv) == 4 and argv[1] == "parse":
        text = Path(argv[2]).read_text(encoding="utf-8")
        write_json(argv[3], parse_article(text))
    elif len(argv) == 4 and argv[1] == "serialize":
        article = read_json(argv[2])
        Path(argv[3]).write_text(serialize_article(article), encoding="utf-8")
    else:
        usage(argv[0] if argv else "article_format.py",
             ["parse <draft.md> <out.json>", "serialize <article.json> <out.md>"])


if __name__ == "__main__":
    main(sys.argv)
