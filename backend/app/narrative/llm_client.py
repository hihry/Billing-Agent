"""
LLM client. Defined as a Protocol (structural interface) rather than a
concrete class, specifically so tests can inject a fake client that
returns scripted responses — the grounding validator is what actually
needs thorough testing, not a real network call to an LLM provider.

The brief says "any LLM API is fine." This uses OpenRouter (OpenAI-
compatible chat completions API), which gives access to free-tier models —
swapping providers again only requires a new class implementing generate().
"""

from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Returns the raw text response. Callers are responsible for
        parsing/validating it — this layer does no interpretation."""
        ...


class OpenRouterLLMClient:
    """
    OpenRouter's API is OpenAI-compatible: POST /chat/completions with a
    messages array, response shape is response['choices'][0]['message'].

    NOTE on `enable_reasoning`: OpenRouter supports a multi-turn flow where
    a model's `reasoning_details` from one response gets threaded back into
    the next request so the model "continues thinking" across turns. Our
    orchestration (app/narrative/service.py) doesn't need that — each
    retry sends a FRESH, independent prompt (the original report + a note
    about which numbers were invented), not a continuation of the same
    conversation. So reasoning_details is intentionally not preserved
    between calls here; each generate() call is stateless. Reasoning is
    left OFF by default for narrative generation, since it adds latency
    and extra tokens without helping a short grounded-summary task — flip
    it on via the constructor if a specific model benefits from it.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "liquid/lfm-2.5-2.6b:free",
        enable_reasoning: bool = False,
        timeout: float = 30.0,
    ):
        self._api_key = api_key
        self._model = model
        self._enable_reasoning = enable_reasoning
        self._timeout = timeout

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        import requests  # imported lazily so the package is optional
        # unless this client is actually constructed (e.g. fallback-only
        # deployments don't need the dependency installed at all).

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if self._enable_reasoning:
            payload["reasoning"] = {"enabled": True}

        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self._timeout,
        )
        response.raise_for_status()  # network/auth/rate-limit errors surface
        # as exceptions here, which app/narrative/service.py already
        # catches broadly and routes to the deterministic fallback — no
        # special-casing needed on top of what's already there.

        data = response.json()
        choices = data.get("choices")
        if not choices:
            raise ValueError(f"OpenRouter response had no 'choices': {data}")

        message = choices[0].get("message", {})
        content = message.get("content")
        if not content:
            raise ValueError(f"OpenRouter response had empty content: {data}")

        return content
