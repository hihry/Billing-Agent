"""
Deterministic, template-based narrative. No LLM involved at all — this is
the safety net that makes "zero invented numbers" a guarantee rather than
a best-effort. It's used when: the LLM is unavailable/unconfigured, its
response is malformed/off-schema, or it fails to ground even after one
retry.

Every number here is an f-string interpolation of a report field, so by
construction it can never diverge from the report — there's no parsing,
no free text generation, nothing that could introduce an invented figure.
"""

from __future__ import annotations

from decimal import Decimal

from app.narrative.schemas import CitedFigure, NarrativeContent


def _rupee(paise: int) -> str:
    rupees = Decimal(abs(paise)) / 100
    sign = "-" if paise < 0 else ""
    if rupees == rupees.to_integral_value():
        return f"{sign}₹{int(rupees):,}"
    return f"{sign}₹{rupees:,.2f}"


def fallback_template_narrative(reconciliation: dict, analytics: dict) -> NarrativeContent:
    lines: list[str] = []
    cited: list[CitedFigure] = []

    lines.append(
        f"{_rupee(reconciliation['total_billed_paise'])} billed across "
        f"{reconciliation['visit_count']} visits, "
        f"{_rupee(reconciliation['total_collected_paise'])} collected."
    )
    cited.append(CitedFigure(value=_rupee(reconciliation["total_billed_paise"]), source_field="total_billed_paise"))
    cited.append(CitedFigure(value=str(reconciliation["visit_count"]), source_field="visit_count"))
    cited.append(CitedFigure(value=_rupee(reconciliation["total_collected_paise"]), source_field="total_collected_paise"))

    if reconciliation["outstanding_paise"] > 0:
        lines.append(
            f"{_rupee(reconciliation['outstanding_paise'])} still outstanding across "
            f"{reconciliation['outstanding_visit_count']} visit(s)."
        )
        cited.append(CitedFigure(value=_rupee(reconciliation["outstanding_paise"]), source_field="outstanding_paise"))
        cited.append(CitedFigure(value=str(reconciliation["outstanding_visit_count"]), source_field="outstanding_visit_count"))

    if reconciliation["refunds_paise"] > 0:
        lines.append(
            f"{_rupee(reconciliation['refunds_paise'])} refunded across "
            f"{reconciliation['refund_visit_count']} visit(s)."
        )
        cited.append(CitedFigure(value=_rupee(reconciliation["refunds_paise"]), source_field="refunds_paise"))
        cited.append(CitedFigure(value=str(reconciliation["refund_visit_count"]), source_field="refund_visit_count"))

    if analytics.get("peak_hour") is not None:
        h = analytics["peak_hour"]
        h12 = h % 12
        h12 = 12 if h12 == 0 else h12
        period = "am" if h < 12 else "pm"
        lines.append(
            f"Busiest hour: {h12}{period}, with {_rupee(analytics['peak_hour_revenue_paise'])} in revenue."
        )
        cited.append(CitedFigure(value=str(h), source_field="peak_hour"))
        cited.append(CitedFigure(value=_rupee(analytics["peak_hour_revenue_paise"]), source_field="peak_hour_revenue_paise"))
    else:
        lines.append("No sales activity recorded today (no non-refund visits).")

    if analytics.get("top_medicines_by_qty"):
        top = analytics["top_medicines_by_qty"][0]
        lines.append(f"Top mover by quantity: {top['drug_name']} ({top['qty']} units).")
        cited.append(CitedFigure(value=str(top["qty"]), source_field="top_medicines_by_qty[0].qty"))

    if analytics.get("top_medicines_by_revenue"):
        top = analytics["top_medicines_by_revenue"][0]
        lines.append(f"Top by revenue: {top['drug_name']} ({_rupee(top['revenue_paise'])}).")
        cited.append(CitedFigure(value=_rupee(top["revenue_paise"]), source_field="top_medicines_by_revenue[0].revenue_paise"))

    lines.append("Note: profit isn't shown here since cost price data wasn't provided.")

    return NarrativeContent(narrative=" ".join(lines), cited_figures=cited)