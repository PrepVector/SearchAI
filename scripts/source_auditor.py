#!/usr/bin/env python3
"""source-auditor — deterministic credibility/duplication pass over
evidence-scout's findings. No model call: this is a mechanical dedupe +
domain-heuristic step, not a judgement call, per the design rule that
simple structural/quality facts should never depend entirely on an LLM.

Usage:
  python3 source_auditor.py audit <findings.json> <sources.json> <out.json>
"""
from __future__ import annotations

import sys
from urllib.parse import urlparse

from _jsonio import read_json, write_json, usage

_LOW_TRUST_HINTS = ("pinterest.", "quora.", "medium.com/@", "reddit.com/r/",
                    "content-farm", "listicle")
_HIGH_TRUST_HINTS = (".gov", ".edu", "arxiv.org", "official", "docs.")


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _dedupe(findings: list[dict]) -> tuple[list[dict], int]:
    seen = set()
    out = []
    dupes = 0
    for f in findings:
        key = (f.get("claim", "").strip().lower()[:120], _domain(f.get("source_url", "")))
        if key in seen:
            dupes += 1
            continue
        seen.add(key)
        out.append(f)
    return out, dupes


def audit(findings: list[dict], sources: list[dict]) -> dict:
    deduped, dupes = _dedupe(findings)
    annotated = []
    low_trust = 0
    for f in deduped:
        domain = _domain(f.get("source_url", ""))
        hint = "unrated"
        if any(h in domain for h in _HIGH_TRUST_HINTS):
            hint = "high"
        elif any(h in domain for h in _LOW_TRUST_HINTS):
            hint = "low"
            low_trust += 1
        annotated.append({**f, "source_domain": domain, "credibility_hint": hint})
    domains = {_domain(s.get("url", "")) for s in sources if s.get("url")}
    notes = []
    if dupes:
        notes.append(f"{dupes} duplicate finding(s) removed.")
    if low_trust:
        notes.append(f"{low_trust} finding(s) from lower-trust domains — flagged, not discarded.")
    return {"findings": annotated, "unique_domains": len(domains),
            "duplicates_removed": dupes, "low_trust_count": low_trust,
            "notes": "; ".join(notes) or "no source-quality issues detected"}


def main(argv: list[str]) -> None:
    if len(argv) != 5 or argv[1] != "audit":
        usage(argv[0] if argv else "source_auditor.py",
             ["audit <findings.json> <sources.json> <out.json>"])
        return
    findings = read_json(argv[2])
    sources = read_json(argv[3])
    write_json(argv[4], audit(findings, sources))


if __name__ == "__main__":
    main(sys.argv)
