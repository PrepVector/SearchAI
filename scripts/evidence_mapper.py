#!/usr/bin/env python3
"""evidence-mapper — maps findings into numbered evidence claims ([E1],
[E2], ...) the writer cites. Deterministic: given evidence-scout's findings
already carry source attribution, mapping is a grouping/formatting problem,
not a judgement call — spending a model call on it would be exactly the
"unnecessary agent" the design rule warns against.

Usage:
  python3 evidence_mapper.py build_map <findings.json> <out.json>
"""
from __future__ import annotations

import sys
from difflib import SequenceMatcher

from _jsonio import read_json, write_json, usage


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def build_map(findings: list[dict]) -> dict:
    grouped: list[list[dict]] = []
    for f in findings:
        placed = False
        for group in grouped:
            if _similar(group[0].get("claim", ""), f.get("claim", "")) > 0.72:
                group.append(f)
                placed = True
                break
        if not placed:
            grouped.append([f])

    evidence = []
    for i, group in enumerate(grouped[:24]):
        primary = group[0]
        domains = {g.get("source_url", "").split("/")[2] if "://" in g.get("source_url", "") else ""
                   for g in group}
        evidence.append({
            "id": f"E{i + 1}",
            "claim": primary.get("claim", ""),
            "detail": primary.get("detail", ""),
            "source_title": primary.get("source_title", ""),
            "source_url": primary.get("source_url", ""),
            "as_of": primary.get("as_of", ""),
            "support": "corroborated" if len(domains - {""}) > 1 else "single-source",
            "echoed_by": len(group),
        })
    return {"evidence": evidence,
            "single_source_count": sum(1 for e in evidence if e["support"] == "single-source")}


def main(argv: list[str]) -> None:
    if len(argv) != 4 or argv[1] != "build_map":
        usage(argv[0] if argv else "evidence_mapper.py",
             ["build_map <findings.json> <out.json>"])
        return
    findings = read_json(argv[2])
    write_json(argv[3], build_map(findings))


if __name__ == "__main__":
    main(sys.argv)
