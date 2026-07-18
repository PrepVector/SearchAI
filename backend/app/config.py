"""SEARCH AI — central configuration.

Every provider, model name and feature flag is read from the environment
(.env). Nothing model-specific is hardcoded so the stack never goes stale.

Alias support: common variable names from earlier SEARCH AI builds are
accepted too (GEMINI_TEXT_MODEL, OPENAI_COMPATIBLE_*, APP_PORT, MIN_IMAGES,
ENABLE_WEB_IMAGES), so an existing .env keeps working.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

_BACKEND = Path(__file__).resolve().parents[1]   # .../SEARCH_AI/backend
_PROJECT = _BACKEND.parent                       # .../SEARCH_AI

ENV_FILE: str | None = None                      # which .env actually loaded


def _parse_env_file(path: Path) -> None:
    """Minimal .env loader — works even if python-dotenv is missing."""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k:
            os.environ.setdefault(k, v)


for _candidate in (_BACKEND / ".env", _PROJECT / ".env",
                   Path.cwd() / ".env"):
    if _candidate.exists():
        try:
            if load_dotenv:
                load_dotenv(_candidate, override=False)
            else:
                _parse_env_file(_candidate)
            ENV_FILE = str(_candidate)
            break
        except Exception:
            continue


def _env(*names: str, default: str = "") -> str:
    """First non-empty environment value among the given alias names."""
    for name in names:
        raw = os.getenv(name)
        if raw is not None and raw.strip():
            return raw.strip()
    return default


def _bool(*names: str, default: bool = False) -> bool:
    raw = _env(*names)
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _int(*names: str, default: int = 0) -> int:
    try:
        return int(_env(*names) or default)
    except ValueError:
        return default


def _float(*names: str, default: float = 0.0) -> float:
    try:
        return float(_env(*names) or default)
    except ValueError:
        return default


def _list(*names: str, default: str = "") -> list[str]:
    return [p.strip() for p in _env(*names, default=default).split(",")
            if p.strip()]


def _order(*names: str, default: str = "") -> list[str]:
    return [p.lower() for p in _list(*names, default=default)]


BUILD = "2026.07.13-18"


class Settings:
    # ---- provider keys -------------------------------------------------
    gemini_api_key: str = _env("GEMINI_API_KEY")
    openai_api_key: str = _env("OPENAI_API_KEY")
    anthropic_api_key: str = _env("ANTHROPIC_API_KEY")
    openai_compat_base_url: str = _env("OPENAI_COMPAT_BASE_URL",
                                       "OPENAI_COMPATIBLE_BASE_URL")
    openai_compat_api_key: str = _env("OPENAI_COMPAT_API_KEY",
                                      "OPENAI_COMPATIBLE_API_KEY")

    tavily_api_key: str = _env("TAVILY_API_KEY")
    exa_api_key: str = _env("EXA_API_KEY")
    serpapi_api_key: str = _env("SERPAPI_API_KEY")
    openalex_email: str = _env("OPENALEX_EMAIL")
    crossref_email: str = _env("CROSSREF_EMAIL")

    # ---- model names + fallback chains (never hardcoded elsewhere) ------
    gemini_model: str = _env("GEMINI_MODEL", "GEMINI_TEXT_MODEL")
    gemini_fallback_models: list[str] = _list("GEMINI_FALLBACK_MODELS",
                                              "GEMINI_TEXT_FALLBACK_MODELS")
    openai_model: str = _env("OPENAI_MODEL", "OPENAI_TEXT_MODEL")
    openai_fallback_models: list[str] = _list("OPENAI_FALLBACK_MODELS",
                                              "OPENAI_TEXT_FALLBACK_MODELS")
    anthropic_model: str = _env("ANTHROPIC_MODEL", "ANTHROPIC_TEXT_MODEL")
    anthropic_fallback_models: list[str] = _list("ANTHROPIC_FALLBACK_MODELS")
    openai_compat_model: str = _env("OPENAI_COMPAT_MODEL",
                                    "OPENAI_COMPATIBLE_MODEL")
    openai_compat_fallback_models: list[str] = _list(
        "OPENAI_COMPAT_FALLBACK_MODELS", "OPENAI_COMPATIBLE_FALLBACK_MODELS")

    gemini_image_model: str = _env("GEMINI_IMAGE_MODEL")
    gemini_image_fallback_models: list[str] = _list("GEMINI_IMAGE_FALLBACK_MODELS")
    openai_image_model: str = _env("OPENAI_IMAGE_MODEL")
    openai_image_fallback_models: list[str] = _list("OPENAI_IMAGE_FALLBACK_MODELS")

    # ---- routing ---------------------------------------------------------
    text_provider_order: list[str] = _order(
        "TEXT_PROVIDER_ORDER", default="anthropic,openai,gemini")
    research_provider_order: list[str] = _order(
        "RESEARCH_PROVIDER_ORDER", default="gemini,openai,anthropic")
    editor_provider_order: list[str] = _order(
        "EDITOR_PROVIDER_ORDER", default="anthropic,openai,gemini")
    validator_provider_order: list[str] = _order(
        "VALIDATOR_PROVIDER_ORDER", default="gemini,anthropic,openai")
    image_provider_order: list[str] = _order(
        "IMAGE_PROVIDER_ORDER", default="gemini,openai")

    # ---- behavior flags ----------------------------------------------------
    premium_quality: bool = _bool("PREMIUM_AI_QUALITY_MODE", default=True)
    enable_referential_images: bool = _bool("ENABLE_REFERENTIAL_IMAGES",
                                            "ENABLE_WEB_IMAGES", default=True)
    enable_deep_image_search: bool = _bool("ENABLE_REFERENCE_DEEP_IMAGE_SEARCH",
                                           default=True)
    max_visual_references: int = _int("MAX_VISUAL_REFERENCES", default=36)
    default_min_images: int = _int("DEFAULT_MIN_IMAGES", "MIN_IMAGES", default=5)
    enable_thinking: bool = _bool("ENABLE_EXTENDED_THINKING", default=True)
    thinking_budget: int = _int("THINKING_BUDGET_TOKENS", default=4096)
    llm_timeout: float = _float("LLM_TIMEOUT_SECONDS", default=180.0)
    search_timeout: float = _float("SEARCH_TIMEOUT_SECONDS",
                                   "HTTP_TIMEOUT_SECONDS", default=30.0)
    host: str = _env("SEARCH_AI_HOST", default="127.0.0.1")
    port: int = _int("SEARCH_AI_PORT", "APP_PORT", default=8712)

    def provider_configured(self, provider: str) -> bool:
        return {
            "gemini": bool(self.gemini_api_key),
            "openai": bool(self.openai_api_key),
            "anthropic": bool(self.anthropic_api_key),
            "openai_compatible": bool(self.openai_compat_base_url and
                                      self.openai_compat_api_key),
        }.get(provider, False)

    def model_chain(self, provider: str) -> list[str]:
        """Primary model + fallback models for a provider, deduped."""
        prim, fallbacks = {
            "gemini": (self.gemini_model, self.gemini_fallback_models),
            "openai": (self.openai_model, self.openai_fallback_models),
            "anthropic": (self.anthropic_model, self.anthropic_fallback_models),
            "openai_compatible": (self.openai_compat_model,
                                  self.openai_compat_fallback_models),
        }.get(provider, ("", []))
        chain, seen = [], set()
        for m in [prim, *fallbacks]:
            if m and m not in seen:
                seen.add(m)
                chain.append(m)
        return chain

    def image_model_chain(self, provider: str) -> list[str]:
        prim, fallbacks = {
            "gemini": (self.gemini_image_model, self.gemini_image_fallback_models),
            "openai": (self.openai_image_model, self.openai_image_fallback_models),
        }.get(provider, ("", []))
        chain, seen = [], set()
        for m in [prim, *fallbacks]:
            if m and m not in seen:
                seen.add(m)
                chain.append(m)
        return chain

    def any_text_provider(self) -> bool:
        return any(self.provider_configured(p) and self.model_chain(p)
                   for p in ("gemini", "openai", "anthropic",
                             "openai_compatible"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
