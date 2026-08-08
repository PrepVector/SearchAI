#!/usr/bin/env python3
"""visual-contract — the deterministic counterpart to outline_contract.py,
but for images instead of text structure. visual-curator decides WHICH
sections deserve a visual and what kind; this script checks the
structural facts about what it actually produced — every image has a
caption, its section_id points at a real outline section, no two images
in the same section repeat the same archetype/concept, and the count
never exceeds the approved cap. None of that benefits from being
re-judged by a model, so — same design principle as the rest of
scripts/ — code decides, the model proposes.

Runs AFTER visual-curator (visuals don't exist before then), so this is
part of final validation, not something the pre-visual quality-auditor
pass can check.

Usage:
  python3 visual_contract.py audit <images.json> <outline.json> <image_cap> <out.json>
"""
from __future__ import annotations

import sys

from _jsonio import read_json, write_json, usage


def audit(images: list[dict], outline: dict, image_cap: int) -> dict:
    """Returns {"score": 0-100, "issues": [...]} — score starts at 100 and
    loses points for each structural problem found; issues are plain-
    language strings suitable for a person to read directly."""
    issues: list[str] = []
    valid_ids = {s.get("id") for s in outline.get("sections", []) if s.get("id")}

    if image_cap and len(images) > image_cap:
        issues.append(f"{len(images)} visuals placed, above the approved cap of {image_cap}.")

    seen_per_section: dict[str, set] = {}
    for img in images:
        sec_id = img.get("section_id", "")
        caption = (img.get("caption") or "").strip()
        archetype = img.get("archetype") or ""

        if not caption:
            issues.append(f"A visual in section '{sec_id or 'unassigned'}' is missing a caption.")
        if sec_id and valid_ids and sec_id not in valid_ids:
            issues.append(f"A visual references section '{sec_id}', which isn't in the "
                          "approved outline — it may be orphaned or misfiled.")
        if not img.get("url"):
            issues.append(f"A visual in section '{sec_id or 'unassigned'}' has no renderable "
                          "image data.")

        bucket = seen_per_section.setdefault(sec_id, set())
        if archetype and archetype in bucket:
            issues.append(f"Section '{sec_id}' has two visuals of the same kind "
                          f"({archetype}) — likely redundant, not reinforcing.")
        bucket.add(archetype)

    score = max(0, 100 - 12 * len(issues))
    return {"score": score, "issues": issues}


def main(argv: list[str]) -> None:
    if len(argv) != 6 or argv[1] != "audit":
        usage(argv[0] if argv else "visual_contract.py",
             ["audit <images.json> <outline.json> <image_cap> <out.json>"])
        return
    images = read_json(argv[2])
    outline = read_json(argv[3])
    try:
        image_cap = int(argv[4])
    except ValueError:
        image_cap = 0
    write_json(argv[5], audit(images, outline, image_cap))


if __name__ == "__main__":
    main(sys.argv)
