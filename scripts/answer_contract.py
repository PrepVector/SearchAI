#!/usr/bin/env python3
"""Answer Contract — the internal spec the writer writes against and the
quality-auditor audits against, so the two can never silently drift apart
on what "done" means for this specific research request. Deterministic:
normalizes the research-planner's proposed contract and applies the user's
own option caps (depth/format/sources/visuals) as hard ceilings the
planner's judgement cannot exceed.

Usage:
  python3 answer_contract.py build <raw_contract.json> <options.json> <topic.txt> <out.json>
  python3 answer_contract.py coverage_gaps <contract.json> <outline_sections.json> <out.json>
"""
from __future__ import annotations

import sys
from pathlib import Path

from _jsonio import read_json, write_json, usage


def build(topic: str, raw: dict, options: dict) -> dict:
    c = raw or {}
    return {
        "main_question": str(c.get("main_question") or topic).strip(),
        "subquestions": [str(x).strip() for x in (c.get("subquestions") or []) if str(x).strip()][:8],
        "required_sections": [str(x).strip() for x in (c.get("required_sections") or []) if str(x).strip()],
        "requested_depth": c.get("requested_depth") or options.get("depth", "standard"),
        "audience": c.get("audience") or options.get("audience", "professional/technical"),
        "format": options.get("format", c.get("format", "auto")),
        "source_requirements": c.get("source_requirements") or options.get("source_preferences", ""),
        "recency_requirements": bool(c.get("recency_requirements", options.get("current_findings", True))),
        "visual_requirements": c.get("visual_requirements") or options.get("visual_preferences", ""),
        "user_constraints": [str(x).strip() for x in (c.get("user_constraints") or []) if str(x).strip()],
    }


def coverage_gaps(contract: dict, outline_sections: list[dict]) -> list[str]:
    gaps: list[str] = []
    haystack = " ".join(
        (s.get("title", "") + " " + s.get("goal", "") + " " +
         " ".join(s.get("subpoints", []) or []) + " " +
         " ".join(s.get("key_questions", []) or [])).lower()
        for s in outline_sections)
    for rs in contract.get("required_sections", []):
        key_words = [w for w in rs.lower().split() if len(w) > 3]
        if key_words and not any(w in haystack for w in key_words):
            gaps.append(f"Required section '{rs}' has no obvious matching outline section.")
    for sq in contract.get("subquestions", []):
        key_words = [w for w in sq.lower().split() if len(w) > 4][:4]
        if key_words and not any(w in haystack for w in key_words):
            gaps.append(f"Subquestion may be uncovered by the outline: {sq}")
    return gaps


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        usage(argv[0] if argv else "answer_contract.py",
             ["build <raw_contract.json> <options.json> <topic.txt> <out.json>",
              "coverage_gaps <contract.json> <outline_sections.json> <out.json>"])
    cmd = argv[1]
    if cmd == "build" and len(argv) == 6:
        raw = read_json(argv[2])
        options = read_json(argv[3])
        topic = Path(argv[4]).read_text(encoding="utf-8").strip()
        write_json(argv[5], build(topic, raw, options))
    elif cmd == "coverage_gaps" and len(argv) == 5:
        contract = read_json(argv[2])
        sections = read_json(argv[3])
        write_json(argv[4], {"gaps": coverage_gaps(contract, sections)})
    else:
        usage(argv[0],
             ["build <raw_contract.json> <options.json> <topic.txt> <out.json>",
              "coverage_gaps <contract.json> <outline_sections.json> <out.json>"])


if __name__ == "__main__":
    main(sys.argv)
