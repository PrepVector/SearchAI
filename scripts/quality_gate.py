#!/usr/bin/env python3
"""quality-gate — the deterministic decision layer over quality-auditor's
structured verdict. This is what makes "PASS" trustworthy: the auditor (an
LLM) proposes scores, but whether the run gets to ship as PASS, PASS WITH
WARNINGS, or FAIL — and whether another repair pass is worth running — is
decided by fixed thresholds in code, not by asking the model to grade its
own homework.

Serious factual/citation failures can never silently become PASS: even
once the repair-iteration cap is hit and the run must stop, the reported
status still reflects reality.

Usage:
  python3 quality_gate.py evaluate <verdict.json> <iters_done> <max_iters> <out.json>
"""
from __future__ import annotations

import sys

from _jsonio import read_json, write_json, usage

_CATEGORIES = ["topic_alignment", "answer_contract_coverage", "evidence_support",
              "citation_integrity", "source_quality", "depth", "clarity",
              "coherence", "redundancy"]

HARD_FAIL = {
    "citation_integrity": 50,
    "evidence_support": 50,
    "topic_alignment": 55,
}
MAX_UNSUPPORTED_CLAIMS = 5
MAX_INVENTED_ENTITIES = 3

WARN_FLOOR = 85
REPAIR_FLOOR = 70


def _hard_fail_reasons(scores: dict, unsupported: list, invented: list) -> list[str]:
    reasons = []
    for cat, floor in HARD_FAIL.items():
        if scores.get(cat, 100) < floor:
            reasons.append(f"{cat} scored {scores.get(cat):.0f} (< {floor})")
    if len(unsupported) >= MAX_UNSUPPORTED_CLAIMS:
        reasons.append(f"{len(unsupported)} unsupported claims (>= {MAX_UNSUPPORTED_CLAIMS})")
    if len(invented) >= MAX_INVENTED_ENTITIES:
        reasons.append(f"{len(invented)} invented entities (>= {MAX_INVENTED_ENTITIES})")
    return reasons


def evaluate(verdict: dict, iters_done: int, max_iters: int) -> dict:
    scores = {k: float(verdict.get("scores", {}).get(k, 75)) for k in _CATEGORIES}
    unsupported = verdict.get("unsupported_claims", []) or []
    invented = verdict.get("invented_entities", []) or []
    missing = verdict.get("missing_in_scope", []) or []

    hard_reasons = _hard_fail_reasons(scores, unsupported, invented)
    worst = min(scores.values()) if scores else 100
    cap_reached = iters_done >= max_iters

    if hard_reasons:
        status = "fail"
    elif worst < WARN_FLOOR or unsupported or invented or missing:
        status = "pass_with_warnings"
    else:
        status = "pass"

    if status == "pass" or cap_reached:
        action = "accept"
    elif worst < REPAIR_FLOOR or hard_reasons:
        action = "rewrite"
    else:
        action = "polish"

    focus_sections = [d.get("section_id") for d in verdict.get("drift_notes", [])
                      if d.get("section_id")]
    reason_bits = hard_reasons or (
        [f"lowest category {worst:.0f}/100"] if worst < WARN_FLOOR else [])
    reason = "; ".join(reason_bits) or "quality threshold met"
    if cap_reached and action == "accept" and status != "pass":
        reason = f"repair cap ({max_iters}) reached — shipping as {status}: " + reason

    return {"status": status, "action": action, "reason": reason,
            "focus_sections": focus_sections, "hard_fail_reasons": hard_reasons,
            "worst_category_score": worst, "scores": scores}


def display_status(status: str, score: float) -> str:
    label = {"pass": "PASS", "pass_with_warnings": "PASS WITH WARNINGS",
             "fail": "FAIL"}.get(status, status.upper())
    return f"{label} · overall quality {score:.0f}/100"


def main(argv: list[str]) -> None:
    if len(argv) != 6 or argv[1] != "evaluate":
        usage(argv[0] if argv else "quality_gate.py",
             ["evaluate <verdict.json> <iters_done> <max_iters> <out.json>"])
        return
    verdict = read_json(argv[2])
    iters_done = int(argv[3])
    max_iters = int(argv[4])
    result = evaluate(verdict, iters_done, max_iters)
    overall = sum(result["scores"].values()) / len(result["scores"]) if result["scores"] else 0.0
    result["display_status"] = display_status(result["status"], overall)
    result["overall_score"] = round(overall, 1)
    write_json(argv[5], result)


if __name__ == "__main__":
    main(sys.argv)
