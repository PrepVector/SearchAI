"""LLM gateway — routes each agent role through provider + model chains.

Roles: research / writer / editor / validator. Each role has a provider
order from .env; each provider has a model chain (primary + fallbacks) from
.env. The gateway walks provider -> model until one answers, failing fast on
auth errors and retrying once on rate limits / transient 5xx.
Model names come exclusively from .env so nothing here ever goes stale.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx

from ..config import get_settings

ROLE_ORDERS = {
    "research": "research_provider_order",
    "writer": "text_provider_order",
    "editor": "editor_provider_order",
    "validator": "validator_provider_order",
}


class LLMError(RuntimeError):
    pass


async def _call_gemini(model: str, system: str, user: str,
                       max_tokens: int, temperature: float,
                       json_mode: bool = False,
                       timeout: float | None = None) -> str:
    s = get_settings()
    timeout = timeout or s.llm_timeout
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={s.gemini_api_key}")
    gen_cfg: dict = {"maxOutputTokens": max_tokens,
                     "temperature": temperature}
    if json_mode:
        # native structured output — thinking models then emit clean JSON
        gen_cfg["responseMimeType"] = "application/json"
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": gen_cfg,
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError) as exc:
        raise LLMError(f"no text in response ({str(data)[:160]})") from exc
    # skip "thought" parts (thinking models interleave reasoning with the
    # final answer — concatenating both corrupts JSON output)
    text = "".join(p.get("text", "") for p in parts
                   if not p.get("thought"))
    if not text.strip():
        text = "".join(p.get("text", "") for p in parts)
    if not text.strip():
        raise LLMError("empty response")
    return text


async def _call_openai_like(base_url: str, api_key: str, model: str,
                            system: str, user: str, max_tokens: int,
                            temperature: float,
                            timeout: float | None = None) -> str:
    s = get_settings()
    timeout = timeout or s.llm_timeout
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(f"{base_url.rstrip('/')}/chat/completions",
                              json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    try:
        text = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError) as exc:
        raise LLMError(f"no text in response ({str(data)[:160]})") from exc
    if not text.strip():
        raise LLMError("empty response")
    return text


async def _call_anthropic(model: str, system: str, user: str,
                          max_tokens: int, temperature: float,
                          timeout: float | None = None,
                          thinking_budget: int | None = None) -> str:
    s = get_settings()
    timeout = timeout or s.llm_timeout
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    if thinking_budget:
        payload["thinking"] = {"type": "enabled",
                               "budget_tokens": thinking_budget}
        payload["temperature"] = 1
        payload["max_tokens"] = max(max_tokens, thinking_budget + 3000)
    headers = {"x-api-key": s.anthropic_api_key,
               "anthropic-version": "2023-06-01"}
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post("https://api.anthropic.com/v1/messages",
                              json=payload, headers=headers)
        if r.status_code == 400 and thinking_budget:
            payload.pop("thinking", None)          # model lacks thinking
            payload["temperature"] = temperature
            payload["max_tokens"] = max_tokens
            r = await client.post("https://api.anthropic.com/v1/messages",
                                  json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    text = "".join(b.get("text", "") for b in data.get("content", [])
                   if isinstance(b, dict) and b.get("type") == "text")
    if not text.strip():
        raise LLMError(f"no text in response ({str(data)[:160]})")
    return text


async def _dispatch(provider: str, model: str, system: str, user: str,
                    max_tokens: int, temperature: float,
                    json_mode: bool = False,
                    timeout: float | None = None,
                    thinking_budget: int | None = None) -> str:
    s = get_settings()
    if provider == "gemini":
        return await _call_gemini(model, system, user, max_tokens,
                                  temperature, json_mode, timeout)
    if provider == "openai":
        return await _call_openai_like("https://api.openai.com/v1",
                                       s.openai_api_key, model,
                                       system, user, max_tokens, temperature,
                                       timeout)
    if provider == "anthropic":
        return await _call_anthropic(model, system, user, max_tokens,
                                     temperature, timeout,
                                     thinking_budget=thinking_budget)
    if provider == "openai_compatible":
        return await _call_openai_like(s.openai_compat_base_url,
                                       s.openai_compat_api_key, model,
                                       system, user, max_tokens, temperature,
                                       timeout)
    raise LLMError(f"unknown provider '{provider}'")


async def chat(role: str, system: str, user: str, *,
               max_tokens: int = 4096, temperature: float = 0.5,
               expect_json: bool = False, thinking: bool = False) -> str:
    """Route a prompt to the provider/model chain for the given role.
    With expect_json, unparseable output counts as a model failure and the
    chain falls through to the next model/provider automatically."""
    s = get_settings()
    order = getattr(s, ROLE_ORDERS.get(role, "text_provider_order"))
    errors: list[str] = []
    any_configured = False
    # small structured calls must fail fast, not hold a 3-minute leash
    if max_tokens <= 1400:
        call_timeout = min(60.0, s.llm_timeout)
    elif max_tokens <= 3600:
        call_timeout = min(100.0, s.llm_timeout)
    else:
        call_timeout = s.llm_timeout

    for provider in order:
        if not s.provider_configured(provider):
            continue
        chain = s.model_chain(provider)[:4]  # bound worst-case latency
        if not chain:
            errors.append(f"{provider}: no model name set in .env")
            continue
        any_configured = True
        auth_dead = False
        for model in chain:
            if auth_dead:
                break
            for attempt in (0, 1):
                try:
                    tb = (s.thinking_budget
                          if thinking and s.enable_thinking else None)
                    text = await _dispatch(provider, model, system, user,
                                           max_tokens, temperature,
                                           json_mode=expect_json,
                                           timeout=call_timeout,
                                           thinking_budget=tb)
                    if expect_json:
                        try:
                            parsed = extract_json(text)
                        except LLMError:
                            errors.append(f"{provider}/{model}: unparseable "
                                          f"JSON: {text[:120]!r}")
                            break          # try the next model in the chain
                        if coerce_json_object(parsed) is None:
                            errors.append(f"{provider}/{model}: JSON was not "
                                          f"an object: {text[:120]!r}")
                            break          # try the next model in the chain
                    return text
                except httpx.HTTPStatusError as exc:
                    code = exc.response.status_code
                    errors.append(f"{provider}/{model}: HTTP {code}")
                    if code in (401, 403):
                        auth_dead = True   # key is bad — skip whole provider
                        break
                    if code in (429, 500, 502, 503, 529) and attempt == 0:
                        await asyncio.sleep(1.2)
                        continue           # one retry on the same model
                    break                  # 404/400/etc — try next model
                except Exception as exc:   # noqa: BLE001 — network/parse
                    errors.append(f"{provider}/{model}: "
                                  f"{type(exc).__name__}: {str(exc)[:120]}")
                    break

    detail = "; ".join(errors)[-700:] if errors else "no providers configured"
    if not any_configured:
        raise LLMError("No LLM provider answered. Configure at least one "
                       "key + model in .env. " + detail)
    raise LLMError("All configured providers/models failed. " + detail)


def coerce_json_object(value):
    """Agents always expect a JSON object. JSON-mode models sometimes wrap
    it in a top-level array ([{...}]) or split it across several objects.
    Unwrap/merge when unambiguous; return None if it cannot be an object."""
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        dicts = [v for v in value if isinstance(v, dict)]
        if len(dicts) == 1:
            return dicts[0]
        if dicts and len(dicts) == len(value):
            merged: dict = {}
            for d in dicts:
                for k, v in d.items():
                    if k in merged:
                        return None          # ambiguous — not coercible
                    merged[k] = v
            return merged or None
    return None


_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> Any:
    """Robustly extract the first JSON object/array from model output."""
    text = text.strip()
    m = _JSON_FENCE.search(text)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        while start != -1:
            depth = 0
            in_str = False
            esc = False
            for i in range(start, len(text)):
                c = text[i]
                if in_str:
                    if esc:
                        esc = False
                    elif c == "\\":
                        esc = True
                    elif c == '"':
                        in_str = False
                    continue
                if c == '"':
                    in_str = True
                elif c == opener:
                    depth += 1
                elif c == closer:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i + 1])
                        except json.JSONDecodeError:
                            break
            start = text.find(opener, start + 1)
    raise LLMError("Model did not return parseable JSON.")


async def chat_json(role: str, system: str, user: str, *,
                    max_tokens: int = 4096, temperature: float = 0.4) -> Any:
    system = (system + "\n\nReturn ONLY valid JSON. No prose, no markdown "
              "fences, no commentary before or after the JSON.")
    raw = await chat(role, system, user, max_tokens=max_tokens,
                     temperature=temperature, expect_json=True)
    return coerce_json_object(extract_json(raw))
