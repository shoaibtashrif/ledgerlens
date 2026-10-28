"""LLM provider layer. Groq, OpenAI and Ollama all speak the OpenAI API,
so one client covers all three; the router handles fallback order."""
from __future__ import annotations

import time
from dataclasses import dataclass

import openai
from openai import OpenAI

from .config import settings


class ProviderError(Exception):
    """Raised with a human-readable message."""


@dataclass
class LLMResult:
    content: str
    provider: str
    model: str
    latency_ms: int
    tokens_in: int
    tokens_out: int

    @property
    def cost_usd(self) -> float | None:
        price = settings.raw.get("pricing", {}).get(self.model)
        if not price:
            return None
        return round(self.tokens_in / 1e6 * price[0] + self.tokens_out / 1e6 * price[1], 6)


def client_for(name: str, key: str | None = None) -> OpenAI:
    cfg = settings.provider(name)
    api_key = key or settings.get_key(name) or ("ollama" if not cfg.get("requires_key") else None)
    if not api_key:
        raise ProviderError(f"No API key for {cfg['label']}. Add it in Settings.")
    return OpenAI(api_key=api_key, base_url=cfg["base_url"], timeout=cfg.get("timeout", 60), max_retries=2)


def candidates(vision: bool, only: str | None = None, exclude: set[str] | None = None) -> list[tuple[str, str]]:
    """(provider, model) pairs in fallback order that can handle this input."""
    out = []
    for name in settings.provider_order:
        if only and name != only:
            continue
        if exclude and name in exclude:
            continue
        if not settings.is_available(name):
            continue
        model = settings.model_for(name, vision)
        if model:
            out.append((name, model))
    return out


def friendly_error(e: Exception, label: str) -> str:
    if isinstance(e, openai.AuthenticationError):
        return f"{label}: API key rejected (401). Re-check the key in Settings."
    if isinstance(e, openai.RateLimitError):
        return f"{label}: Rate limit reached (free tier limit). Please wait 10-15 seconds and click 'Retry Processing'."
    if isinstance(e, openai.NotFoundError):
        return f"{label}: model not found. Pick another model in Settings."
    if isinstance(e, openai.APITimeoutError):
        return f"{label}: request timed out."
    if isinstance(e, openai.APIConnectionError):
        return f"{label}: cannot connect (offline or service down)."
    if isinstance(e, openai.APIStatusError):
        return f"{label}: HTTP {e.status_code} — {str(e)[:160]}"
    return f"{label}: {str(e)[:200]}"


def chat(name: str, model: str, messages: list[dict], json_mode: bool = True) -> LLMResult:
    cfg = settings.provider(name)
    client = client_for(name)
    kwargs: dict = {"model": model, "messages": messages, "temperature": 0}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if cfg.get("extra_body"):
        kwargs["extra_body"] = cfg["extra_body"]

    t0 = time.perf_counter()
    try:
        resp = client.chat.completions.create(**kwargs)
    except openai.RateLimitError:
        # Wait 3 seconds for token window and retry once
        time.sleep(3)
        resp = client.chat.completions.create(**kwargs)
    except openai.BadRequestError:
        # Some models reject json mode / reasoning params: retry once with a plain request.
        kwargs.pop("response_format", None)
        kwargs.pop("extra_body", None)
        resp = client.chat.completions.create(**kwargs)
    latency = int((time.perf_counter() - t0) * 1000)

    usage = getattr(resp, "usage", None)
    return LLMResult(
        content=resp.choices[0].message.content or "",
        provider=name,
        model=model,
        latency_ms=latency,
        tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
        tokens_out=getattr(usage, "completion_tokens", 0) or 0,
    )


def test_key(name: str, key: str | None) -> list[str]:
    """Validate a key by listing models. Returns model ids."""
    cfg = settings.provider(name)
    try:
        models = client_for(name, key).models.list()
        return sorted(m.id for m in models.data)
    except Exception as e:  # noqa: BLE001
        raise ProviderError(friendly_error(e, cfg["label"])) from e
