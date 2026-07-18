"""Hard Outline Contract Editor — the approved outline is law.

Deterministically enforces: same section ids/titles, same order, no extra
top-level sections, missing sections restored. If a writer/editor drifted,
this engine repairs the structure and reports an alignment score.
"""
from __future__ import annotations

import difflib


def _match(section: dict, contract_sections: list[dict]) -> int | None:
    """Match a produced section to a contract section by id then fuzzy title."""
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
        else:  # duplicate match — merge body into the first
            slots[idx]["markdown"] += "\n\n" + sec.get("markdown", "")
            notes.append(f"Merged duplicate section into '{contract[idx]['title']}'.")

    # Fold extra top-level sections into the nearest contract section
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
