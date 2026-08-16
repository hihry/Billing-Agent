
from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Returns the raw text response. Callers are responsible for
        parsing/validating it — this layer does no interpretation."""
        ...


class AnthropicLLMClient:
    def __init__(self, api_key: str, model: str = "qwen/qwen3-reranker-8b"):
        import openai  # imported lazily so the package is optional
        # unless this client is actually constructed (e.g. fallback-only
        # deployments don't need the dependency installed at all).

        self._client = openai.OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            # default_headers={
            #     "HTTP-Referer": "http://localhost",  # Replace with your production URL
            #     "X-Title": "Local Development",      # Replace with your app name
            # },
        )
        self._model = model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=600,
        )
        return response.choices[0].message.content or ""

