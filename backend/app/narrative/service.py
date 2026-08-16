"""
Orchestrates the narrative generation flow:

    generate (LLM) -> parse JSON -> validate schema -> validate GROUNDING
        -> if ungrounded: retry ONCE with the specific bad numbers flagged
        -> if still ungrounded, malformed, off-schema, or LLM unavailable:
           fall back to the deterministic template (always grounded)

This is plain Python, not a graph/agent framework — the actual
correctness guarantee (zero invented numbers) comes from grounding.py's
deterministic validation, which is the same code path regardless of how
the LLM call itself is orchestrated. A LangGraph wrapper could sit around
this exact sequence if you want the "agent" framing for the README, but
it wouldn't change what makes this correct.

grounding_status values (stored alongside the narrative, useful for
debugging/demoing which path was taken):
  - "llm_grounded"                        first LLM attempt passed validation
  - "llm_retry_grounded"                  needed one retry, then passed
  - "fallback_no_llm_configured"          no API key/client available
  - "fallback_malformed_response"         LLM output wasn't valid JSON / off-schema
  - "fallback_ungrounded_after_retry"     LLM invented numbers twice in a row
"""

from __future__ import annotations

import json

from pydantic import ValidationError

from app.narrative.fallback import fallback_template_narrative
from app.narrative.grounding import build_whitelist, validate_narrative
from app.narrative.llm_client import LLMClient
from app.narrative.prompts import build_prompt, build_retry_prompt
from app.narrative.schemas import NarrativeContent


def _parse_llm_json(raw: str) -> dict:
    """LLMs frequently wrap JSON in markdown fences despite instructions
    not to — strip that defensively before parsing."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def generate_narrative(
    reconciliation: dict,
    analytics: dict,
    clinic_id: str,
    log_date: str,
    llm_client: LLMClient | None,
) -> tuple[NarrativeContent, str]:
    """Returns (content, grounding_status). NEVER raises — every failure
    mode resolves to the deterministic fallback, which is always grounded
    by construction.

    IMPORTANT: this covers failures in build_whitelist()/build_prompt()
    too, not just the LLM call itself — a malformed report shape or an
    unparseable log_date must still degrade to the fallback template, not
    bubble up as a 500. (This used to be a real bug: those two calls sat
    outside the try/except, silently breaking the "never raises" promise
    this docstring makes. Fixed by wrapping the whole flow.)"""

    if llm_client is None:
        return fallback_template_narrative(reconciliation, analytics), "fallback_no_llm_configured"

    try:
        whitelist = build_whitelist(reconciliation, analytics, log_date)
        system_prompt, user_prompt = build_prompt(reconciliation, analytics, clinic_id, log_date)
    except Exception:
        # A report-shape or date-parsing problem, not an LLM problem —
        # but the outcome must be identical: degrade to the fallback,
        # never surface as a 500.
        return fallback_template_narrative(reconciliation, analytics), "fallback_malformed_response"

    # --- attempt 1 ---
    try:
        raw = llm_client.generate(system_prompt, user_prompt)
        parsed = _parse_llm_json(raw)
        content = NarrativeContent(**parsed)
    except (json.JSONDecodeError, ValidationError, TypeError, KeyError):
        return fallback_template_narrative(reconciliation, analytics), "fallback_malformed_response"
    except Exception:
        # Catch-all for LLM SDK/network failures — never let a narrative
        # request 500 just because the LLM provider had an outage.
        return fallback_template_narrative(reconciliation, analytics), "fallback_malformed_response"

    try:
        ok, invented = validate_narrative(content.narrative, whitelist)
    except Exception:
        return fallback_template_narrative(reconciliation, analytics), "fallback_malformed_response"

    if ok:
        return content, "llm_grounded"

    # --- attempt 2: one retry, telling the model exactly what it got wrong ---
    try:
        retry_prompt = build_retry_prompt(user_prompt, invented)
        raw2 = llm_client.generate(system_prompt, retry_prompt)
        parsed2 = _parse_llm_json(raw2)
        content2 = NarrativeContent(**parsed2)
        ok2, _ = validate_narrative(content2.narrative, whitelist)
    except Exception:
        return fallback_template_narrative(reconciliation, analytics), "fallback_ungrounded_after_retry"

    if ok2:
        return content2, "llm_retry_grounded"

    return fallback_template_narrative(reconciliation, analytics), "fallback_ungrounded_after_retry"