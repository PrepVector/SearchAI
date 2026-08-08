"""Tiny shared helper for the deterministic scripts — read JSON file(s) in,
write a JSON result out. Every script in this folder follows the same
convention so agents/commands can call them uniformly:

    python3 scripts/<name>.py <subcommand> <input.json> [more inputs...] <output.json>

Kept dependency-free (Python 3.9+ stdlib only) since this runs on whatever
Python Claude Code's Bash tool finds on the user's machine — no venv, no
pip install, no network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def read_json(path: str):
    p = Path(path)
    if not p.exists():
        die(f"Input file not found: {path}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        die(f"Could not parse '{path}' as JSON: {exc}")


def write_json(path: str, data) -> None:
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def die(message: str) -> None:
    print(json.dumps({"error": message}), file=sys.stderr)
    sys.exit(1)


def usage(script: str, forms: list[str]) -> None:
    lines = [f"Usage: python3 {script} <subcommand> ..."] + [f"  {f}" for f in forms]
    die("\n".join(lines))
