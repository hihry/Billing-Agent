"""
Prompt construction. The LLM sees ONLY the two report dicts — never raw
visit rows — so there's no path for it to compute a number we didn't
already compute deterministically. This is what makes the grounding
validator's job tractable: the model's entire "world" is the JSON we hand it.
"""

from __future__ import annotations

import json

SYSTEM_PROMPT = """You are a clinic billing assistant. You will be given a clinic's \
end-of-day reconciliation and analytics report as JSON. Write a short, warm, \
WhatsApp-style summary for the clinic owner.

STRICT RULES:
1. Use ONLY the numbers present in the JSON below. Do not calculate, round \
differently, estimate, average, or invent any number — including percentages \
or profit figures that aren't directly given.
2. All money in the JSON is in PAISE (e.g. 42850 paise = ₹428.50). Convert to \
rupees using the ₹ symbol and comma thousands separators (e.g. ₹42,850).
3. If a metric can't be computed from the data provided (for example, profit, \
since no cost price is given), say so plainly instead of approximating it as \
something else and presenting it as fact.
4. Respond with ONLY a raw JSON object — no markdown code fences, no preamble, \
no explanation before or after — matching exactly this shape:
{"narrative": "<string>", "cited_figures": [{"value": "<number as shown in the \
narrative, e.g. '42,850'>", "source_field": "<the report field name it came from, \
e.g. 'total_billed_paise'>"}]}
cited_figures must list every number you used in the narrative and which report \
field it came from."""


def build_prompt(
    reconciliation: dict, analytics: dict, clinic_id: str, log_date: str
) -> tuple[str, str]:
    user_prompt = json.dumps(
        {
            "clinic_id": clinic_id,
            "log_date": log_date,
            "reconciliation": reconciliation,
            "analytics": analytics,
        },
        indent=2,
    )
    return SYSTEM_PROMPT, user_prompt


def build_retry_prompt(original_user_prompt: str, invented_numbers: list[str]) -> str:
    return (
        f"{original_user_prompt}\n\n"
        f"Your previous attempt included these numbers, which do NOT appear anywhere "
        f"in the JSON above: {invented_numbers}. Rewrite the summary using ONLY numbers "
        f"that appear in the JSON. Respond with the same raw JSON shape as before."
    )