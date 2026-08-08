#!/usr/bin/env python3
"""Creates a fresh, timestamped run folder under research_runs/ with the
subfolder scaffolding every stage of /run-research writes into. Printing
the resulting path lets the orchestrating command capture it directly.

Usage:
  python3 new_run.py <topic text> [research_runs_dir]
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def slugify(text: str, max_len: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug[:max_len].rstrip("-")) or "topic"


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        print("Usage: python3 new_run.py <topic text> [research_runs_dir]", file=sys.stderr)
        sys.exit(1)
    topic = argv[1]
    base = Path(argv[2]) if len(argv) > 2 else Path(__file__).resolve().parents[1] / "research_runs"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = base / f"{stamp}_{slugify(topic)}"
    for sub in ("evidence", "outline", "draft", "audit", "visuals", "output"):
        (run_dir / sub).mkdir(parents=True, exist_ok=True)
    (run_dir / "topic.txt").write_text(topic.strip() + "\n", encoding="utf-8")
    print(str(run_dir))


if __name__ == "__main__":
    main(sys.argv)
