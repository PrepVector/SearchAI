#!/usr/bin/env python3
"""Hard Outline Contract — the approved outline is law. Two deterministic
responsibilities (no LLM judgement for structural facts):

1. structural_audit — BEFORE writing/auditing, checks the outline itself
   against the answer contract: required sections present, no duplicated
   titles, sections wanting visuals/comparisons say so, minimum depth
   indicators present. Findings feed quality-auditor as a signal it can't
   hand-wave past.
2. enforce — AFTER writing, repairs the produced article's structure to
   exactly match the outline (same section ids/titles, same order, no
   extra top-level sections, missing sections restored) and reports an
   alignment score.

Usage:
  python3 outline_contract.py structural_audit <outline.json> <contract.json> <out.json>
  python3 outline_contract.py enforce <article.json> <outline.json> <out.json>
"""
from __future__ import annotations

import difflib
import sys

from _jsonio import read_json, write_json, usage


def structural_audit(outline: dict, contract: dict) -> list[str]:
    issues: list[str] = []
    sections = outline.get("sections", [])
    if len(sections) < 3:
        issues.append(f"Outline has only {len(sections)} section(s) — too thin "
                      "for the requested depth.")

    titles_lower = [s.get("title", "").strip().lower() for s in sections]
    for i, t in enumerate(titles_lower):
        for j, t2 in enumerate(titles_lower):
            if i < j and t and t == t2:
                issues.append(f"Duplicate section title: '{sections[i].get('title')}'.")

    # Newsletter items are intentionally short editorial blurbs, not
    # analytical sections — subpoints/key_questions aren't how depth is
    # signaled there, so this check doesn't apply to that layout.
    if outline.get("layout") != "newsletter":
        for s in sections:
            subpoints = s.get("subpoints") or []
            key_qs = s.get("key_questions") or []
            if not subpoints and not key_qs:
                issues.append(f"Section '{s.get('title')}' has no subpoints or key "
                              "questions — minimum depth indicator missing.")

    required = contract.get("required_sections", []) if contract else []
    haystack = " ".join(titles_lower)
    for rs in required:
        words = [w for w in rs.lower().split() if len(w) > 3]
        if words and not any(w in haystack for w in words):
            issues.append(f"Required section '{rs}' from the answer contract has "
                          "no matching outline section.")

    wants_visual_any = any(s.get("wants_visual") for s in sections)
    visual_req = (contract or {}).get("visual_requirements", "")
    if visual_req and not wants_visual_any:
        issues.append("Answer contract implies visuals would help, but no "
                      "outline section is flagged wants_visual.")

    return issues


def _match(section: dict, contract_sections: list[dict]) -> int | None:
    sid = section.get("id", "")
    for i, c in enumerate(contract_sections):
        if sid and sid == c["id"]:
            return i
    title = (section.get("title") or "").lower().strip()
    best, best_ratio = None, 0.0
    for i, c in enumerate(contract_sections):
        ratio = difflib.SequenceMatcher(None, title, c["title"].lower()).ratio()
        if ratio > best_ratio:
            best, best_ratio = i, ratio
    return best if best_ratio >= 0.55 else None


def enforce(article: dict, outline: dict) -> tuple[dict, float, list[str]]:
    contract = outline.get("sections", [])
    produced = article.get("sections", [])
    notes: list[str] = []

    slots: list[dict | None] = [None] * len(contract)
    extras: list[dict] = []
    for sec in produced:
        idx = _match(sec, contract)
        if idx is None:
            extras.append(sec)
        elif slots[idx] is None:
            slots[idx] = sec
        else:
            slots[idx]["markdown"] += "\n\n" + sec.get("markdown", "")
            notes.append(f"Merged duplicate section into '{contract[idx]['title']}'.")

    for extra in extras:
        target = 0
        title = (extra.get("title") or "").lower()
        best_ratio = 0.0
        for i, c in enumerate(contract):
            ratio = difflib.SequenceMatcher(
                None, title, (c["title"] + " " + c.get("goal", "")).lower()).ratio()
            if ratio > best_ratio:
                target, best_ratio = i, ratio
        if slots[target] is None:
            slots[target] = {"id": contract[target]["id"],
                             "title": contract[target]["title"],
                             "markdown": extra.get("markdown", "")}
        else:
            slots[target]["markdown"] += (
                f"\n\n**{extra.get('title','Additional detail')}.** "
                + extra.get("markdown", ""))
        notes.append(f"Folded extra section '{extra.get('title','?')}' into "
                     f"'{contract[target]['title']}'.")

    filled = 0
    final_sections = []
    for i, c in enumerate(contract):
        sec = slots[i]
        if sec is None:
            body = ("*This section of the approved outline could not be "
                    "completed from the available material. Intended coverage: "
                    + "; ".join(c.get("subpoints", []) or [c.get("goal", "")])
                    + ".*")
            notes.append(f"Restored missing outline section '{c['title']}'.")
        else:
            body = sec.get("markdown", "")
            filled += 1
        final_sections.append({"id": c["id"], "title": c["title"],
                               "markdown": body,
                               "pull_quote": (sec or {}).get("pull_quote")})

    article["sections"] = final_sections
    denom = max(len(contract), 1)
    score = round(100.0 * (filled - 0.5 * len(extras)) / denom, 1)
    score = max(0.0, min(100.0, score))
    return article, score, notes


def main(argv: list[str]) -> None:
    if len(argv) == 5 and argv[1] == "structural_audit":
        outline = read_json(argv[2])
        contract = read_json(argv[3])
        write_json(argv[4], {"gaps": structural_audit(outline, contract)})
    elif len(argv) == 5 and argv[1] == "enforce":
        article = read_json(argv[2])
        outline = read_json(argv[3])
        enforced, score, notes = enforce(article, outline)
        write_json(argv[4], {"article": enforced, "alignment_score": score, "notes": notes})
    else:
        usage(argv[0] if argv else "outline_contract.py",
             ["structural_audit <outline.json> <contract.json> <out.json>",
              "enforce <article.json> <outline.json> <out.json>"])


if __name__ == "__main__":
    main(sys.argv)
