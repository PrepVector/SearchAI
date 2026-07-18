"""SEARCH AI server launcher — run:  python run.py"""
from __future__ import annotations

import uvicorn

from app.config import BUILD, ENV_FILE, get_settings


def main() -> None:
    s = get_settings()
    print("=" * 58)
    print(f"  SEARCH AI  ·  premium multi-model research generator  ·  build {BUILD}")
    print(f"  Open:  http://{s.host}:{s.port}")
    print(f"  Config: {ENV_FILE or '.env NOT FOUND — using defaults'}")
    if not s.any_text_provider():
        print("  WARNING: no LLM API key configured yet — edit .env")
    print("=" * 58)
    uvicorn.run("app.main:app", host=s.host, port=s.port, reload=False)


if __name__ == "__main__":
    main()
