"""
Deterministic analytics engine.

RULE: same as reconciliation.py — no LLM imports, ever. This is ground
truth.
"""

from __future__ import annotations

from collections import defaultdict

from app.models.billing import Visit
from app.models.reports import (
    AnalyticsReport,
    HourlyRevenue,
    MedicineQtyStat,
    MedicineRevenueStat,
)

TOP_N = 5


def compute_analytics(visits: list[Visit]) -> AnalyticsReport:
    revenue_by_hour: dict[int, int] = defaultdict(int)
    qty_by_drug: dict[str, int] = defaultdict(int)
    revenue_by_drug: dict[str, int] = defaultdict(int)

    for v in visits:
        if v.is_refund:
            # Analytics measures genuine business activity ("what moved,
            # when"), not reversals. Refund line items are deliberately
            # excluded here (see AnalyticsReport docstring).
            continue

        hour = v.timestamp.hour
        for li in v.line_items:
            line_revenue = li.qty * li.unit_price_paise
            revenue_by_hour[hour] += line_revenue
            qty_by_drug[li.drug_name] += li.qty
            revenue_by_drug[li.drug_name] += line_revenue

    hourly = [
        HourlyRevenue(hour=h, revenue_paise=r)
        for h, r in sorted(revenue_by_hour.items())
    ]

    if revenue_by_hour:
        peak_hour = max(revenue_by_hour, key=revenue_by_hour.get)
        peak_hour_revenue = revenue_by_hour[peak_hour]
    else:
        peak_hour = None
        peak_hour_revenue = None

    # Tie-break alphabetically by drug_name for deterministic, testable
    # ordering when two drugs have equal qty or equal revenue.
    top_qty = sorted(qty_by_drug.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_N]
    top_revenue = sorted(revenue_by_drug.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_N]

    return AnalyticsReport(
        revenue_by_hour=hourly,
        peak_hour=peak_hour,
        peak_hour_revenue_paise=peak_hour_revenue,
        top_medicines_by_qty=[MedicineQtyStat(drug_name=n, qty=q) for n, q in top_qty],
        top_medicines_by_revenue=[
            MedicineRevenueStat(drug_name=n, revenue_paise=r) for n, r in top_revenue
        ],
    )