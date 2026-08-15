"""
Deterministic reconciliation engine.

RULE: This module must NEVER import anything from app/narrative/. It is
the ground truth that the narrative layer is checked against — if this
file depended on the LLM layer, that guarantee would be meaningless.
"""

from __future__ import annotations

from collections import defaultdict

from app.models.billing import Visit
from app.models.reports import PaymentModeBreakdown, ReconciliationReport


def compute_reconciliation(visits: list[Visit]) -> ReconciliationReport:
    by_mode: dict[str, dict[str, int]] = defaultdict(
        lambda: {"billed": 0, "collected": 0, "outstanding": 0}
    )

    total_refunds = 0
    refund_visit_count = 0
    outstanding_visit_count = 0

    for v in visits:
        mode = v.payment_mode.value
        billed = v.billed_paise
        collected = v.amount_paid_paise

        by_mode[mode]["billed"] += billed
        by_mode[mode]["collected"] += collected

        if v.is_refund:
            total_refunds += abs(collected)
            refund_visit_count += 1
            # Deliberately no outstanding contribution: a refund is a
            # closed/settled event, never "still owed."
        else:
            visit_outstanding = max(billed - collected, 0)
            by_mode[mode]["outstanding"] += visit_outstanding
            if visit_outstanding > 0:
                outstanding_visit_count += 1

    total_billed = sum(m["billed"] for m in by_mode.values())
    total_collected = sum(m["collected"] for m in by_mode.values())
    total_outstanding = sum(m["outstanding"] for m in by_mode.values())

    return ReconciliationReport(
        total_billed_paise=total_billed,
        total_collected_paise=total_collected,
        outstanding_paise=total_outstanding,
        refunds_paise=total_refunds,
        visit_count=len(visits),
        refund_visit_count=refund_visit_count,
        outstanding_visit_count=outstanding_visit_count,
        by_payment_mode={
            mode: PaymentModeBreakdown(
                billed_paise=vals["billed"],
                collected_paise=vals["collected"],
                outstanding_paise=vals["outstanding"],
            )
            for mode, vals in by_mode.items()
        },
    )