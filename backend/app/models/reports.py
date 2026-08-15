"""
Report models — the shape of the deterministic engine's OUTPUT.

These are what the API layer (Step 5) serializes directly to JSON, and
what the narrative layer (Step 6) will treat as its ONLY source of truth
for numbers. Nothing here is derived from an LLM; everything here is
pure arithmetic over validated Visit objects.
"""

from __future__ import annotations

from pydantic import BaseModel


class PaymentModeBreakdown(BaseModel):
    billed_paise: int
    collected_paise: int
    outstanding_paise: int


class ReconciliationReport(BaseModel):
    """
    Business rules baked into this report (decided deliberately, not by
    accident — see engine/reconciliation.py for the reasoning):

    - total_billed_paise includes REFUNDED visits' original billed amount.
      Billing is a historical fact; a refund is a separate event layered
      on top, not a rewrite of history.
    - total_collected_paise can be NEGATIVE on a day with heavy refunds —
      this is correct, not a bug.
    - outstanding_paise ONLY comes from non-refund visits where
      billed > collected. A refunded visit is a closed/settled event and
      can never be "outstanding."
    - refunds_paise is the sum of abs(amount_paid_paise) across all
      is_refund=True visits.
    """
    total_billed_paise: int
    total_collected_paise: int
    outstanding_paise: int
    refunds_paise: int

    visit_count: int
    refund_visit_count: int
    outstanding_visit_count: int  # non-refund visits with billed > collected

    by_payment_mode: dict[str, PaymentModeBreakdown]


class HourlyRevenue(BaseModel):
    hour: int  # 0-23, UTC
    revenue_paise: int


class MedicineQtyStat(BaseModel):
    drug_name: str
    qty: int


class MedicineRevenueStat(BaseModel):
    drug_name: str
    revenue_paise: int


class AnalyticsReport(BaseModel):
    """
    Business rules baked into this report:

    - ALL figures here (revenue_by_hour, top_medicines_*) are computed
      ONLY from non-refund visits. Analytics measures genuine business
      activity ("what moved, when") — a refund line item didn't move
      product out the door today, it reversed a past sale, so it's
      excluded entirely here (unlike the reconciliation report, where
      refunds DO count toward total_billed).
    - Medicine revenue is qty * unit_price_paise per line item, NOT
      discount-adjusted (discount is applied at the visit level in the
      schema, not itemized per drug) — documented assumption.
    - peak_hour is None if there is no non-refund activity at all
      (e.g. an all-refund day).
    """
    revenue_by_hour: list[HourlyRevenue]
    peak_hour: int | None
    peak_hour_revenue_paise: int | None

    top_medicines_by_qty: list[MedicineQtyStat]
    top_medicines_by_revenue: list[MedicineRevenueStat]