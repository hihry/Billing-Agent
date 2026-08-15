"""
The grounding validator: deterministic Python that checks every number in
an LLM-generated narrative against the numbers actually present in the
deterministic report. This is NOT another LLM call — it's plain string/
regex logic, specifically because the brief says grounding is "graded
automatically" and a second LLM's judgment (e.g. a "reflection agent")
is still probabilistic. Code you can unit-test is a stronger guarantee
than a second model's opinion.

Two subtleties this file handles on purpose:

1. HOUR FORMAT MISMATCH: the report stores hours as 24-hour ints (13),
   but a narrative naturally says "1pm". The digit "1" would fail a naive
   check against "13". We whitelist BOTH the 24-hour number and its
   12-hour equivalent for every hour value in the report.

2. DATE MENTIONS: a narrative might say "today's summary (27 Jul 2026)".
   27 and 2026 aren't invented figures, they're just the log's own date —
   so date components are added to the whitelist too, not treated as
   numbers that must trace back to a money/count field.
"""

from __future__ import annotations

import re
from datetime import date as _date
from decimal import Decimal

NUMBER_PATTERN = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _rupee_variants(paise: int) -> set[str]:
    """All string forms we'll accept for a paise amount expressed in rupees."""
    rupees = Decimal(abs(paise)) / 100  # narratives always show money as positive
    variants = {f"{rupees:.2f}", f"{rupees:,.2f}"}
    if rupees == rupees.to_integral_value():
        whole = int(rupees)
        variants.add(str(whole))
        variants.add(f"{whole:,}")
    return variants
    # NOTE (documented limitation): this whitelist is purely numeric — it
    # has no notion of UNITS. A rupee amount that happens to equal a visit
    # count or a quantity (e.g. exactly ₹500 vs "500 visits") will produce
    # a coincidental whitelist collision, and a narrative misusing that
    # number in the wrong context would NOT be caught. Mitigation: the
    # cited_figures field forces the LLM (or fallback template) to declare
    # which report field each number came from, so a reviewer can spot a
    # mismatched claim even when the raw digits happen to line up.


def _count_variants(n: int) -> set[str]:
    return {str(n), f"{n:,}"}


def _hour_variants(hour_24: int) -> set[str]:
    """Both the raw 24-hour value AND its 12-hour numeral (e.g. 13 -> {'13', '1'})."""
    h12 = hour_24 % 12
    h12 = 12 if h12 == 0 else h12
    return {str(hour_24), str(h12)}


def build_whitelist(reconciliation: dict, analytics: dict, log_date: str | None = None) -> set[str]:
    """
    Flatten every legitimate numeric value in the two reports into a set
    of acceptable string forms. This whitelist is the ENTIRE ground truth
    the narrative is checked against — nothing outside these two dicts
    (plus the log's own date) is ever allowed to appear as a number.
    """
    whitelist: set[str] = set()

    for key in ("total_billed_paise", "total_collected_paise", "outstanding_paise", "refunds_paise"):
        if key in reconciliation:
            whitelist |= _rupee_variants(reconciliation[key])

    for mode_data in reconciliation.get("by_payment_mode", {}).values():
        for key in ("billed_paise", "collected_paise", "outstanding_paise"):
            if key in mode_data:
                whitelist |= _rupee_variants(mode_data[key])

    for key in ("visit_count", "refund_visit_count", "outstanding_visit_count"):
        if key in reconciliation:
            whitelist |= _count_variants(reconciliation[key])

    for entry in analytics.get("revenue_by_hour", []):
        whitelist |= _rupee_variants(entry["revenue_paise"])
        whitelist |= _hour_variants(entry["hour"])

    if analytics.get("peak_hour") is not None:
        whitelist |= _hour_variants(analytics["peak_hour"])
        whitelist |= _hour_variants((analytics["peak_hour"] + 1) % 24)  # e.g. the "1pm" in "12pm-1pm"
    if analytics.get("peak_hour_revenue_paise") is not None:
        whitelist |= _rupee_variants(analytics["peak_hour_revenue_paise"])

    for stat in analytics.get("top_medicines_by_qty", []):
        whitelist |= _count_variants(stat["qty"])
    for stat in analytics.get("top_medicines_by_revenue", []):
        whitelist |= _rupee_variants(stat["revenue_paise"])

    if log_date:
        d = _date.fromisoformat(log_date)
        whitelist |= _count_variants(d.day)
        whitelist |= _count_variants(d.month)
        whitelist |= _count_variants(d.year)
        whitelist.add(f"{d.day:02d}")
        whitelist.add(f"{d.month:02d}")

    return whitelist


def extract_numbers(text: str) -> list[str]:
    return NUMBER_PATTERN.findall(text)


def validate_narrative(narrative_text: str, whitelist: set[str]) -> tuple[bool, list[str]]:
    """
    Returns (is_grounded, invented_numbers). A number is "invented" if
    neither its exact form nor its comma-stripped form appears in the
    whitelist. This is intentionally strict — e.g. a self-computed
    percentage ("89% collected") is NOT derivable from the whitelist
    unless 89 happens to also be a real report figure, and gets flagged.
    That's correct per the brief: "use ONLY numbers present in the JSON,"
    which rules out derived/calculated figures too, not just fabricated ones.
    """
    found = extract_numbers(narrative_text)
    invented = []
    for n in found:
        candidates = {n, n.replace(",", "")}
        if not (candidates & whitelist):
            invented.append(n)
    return (len(invented) == 0, invented)