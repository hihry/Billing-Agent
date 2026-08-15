# """
# LLM client. Defined as a Protocol (structural interface) rather than a
# concrete class, specifically so tests can inject a fake client that
# returns scripted responses — the grounding validator is what actually
# needs thorough testing, not a real network call to an LLM provider.

# The brief says "any LLM API is fine." This uses Anthropic's SDK since
# that's the model family available in this environment, but swapping to
# OpenAI/another provider only requires a new class implementing generate().
# """

# from __future__ import annotations

# from typing import Protocol


# class LLMClient(Protocol):
#     def generate(self, system_prompt: str, user_prompt: str) -> str:
#         """Returns the raw text response. Callers are responsible for
#         parsing/validating it — this layer does no interpretation."""
#         ...


# class AnthropicLLMClient:
#     def __init__(self, api_key: str, model: str = "claude-3-5-haiku-latest"):
#         import anthropic  # imported lazily so the package is optional
#         # unless this client is actually constructed (e.g. fallback-only
#         # deployments don't need the dependency installed at all).

#         self._client = anthropic.Anthropic(api_key=api_key)
#         self._model = model

#     def generate(self, system_prompt: str, user_prompt: str) -> str:
#         response = self._client.messages.create(
#             model=self._model,
#             max_tokens=600,
#             system=system_prompt,
#             messages=[{"role": "user", "content": user_prompt}],
#         )
#         return "".join(block.text for block in response.content if block.type == "text")


"""
LLM client. Defined as a Protocol (structural interface) rather than a
concrete class, specifically so tests can inject a fake client that
returns scripted responses — the grounding validator is what actually
needs thorough testing, not a real network call to an LLM provider.

The brief says "any LLM API is fine." This implementation uses OpenRouter
via the OpenAI SDK. The class name 'AnthropicLLMClient' is retained 
strictly for backward compatibility with the rest of the codebase.
"""

from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Returns the raw text response. Callers are responsible for
        parsing/validating it — this layer does no interpretation."""
        ...


class AnthropicLLMClient:
    def __init__(self, api_key: str, model: str = "meta-llama/llama-3-8b-instruct:free"):
        import openai  # imported lazily so the package is optional
        # unless this client is actually constructed (e.g. fallback-only
        # deployments don't need the dependency installed at all).

        self._client = openai.OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "http://localhost", # Replace with your URL in production
                "X-Title": "Local Development",     # Replace with your app name
            }
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