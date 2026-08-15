"""
Tests for app/engine/reconciliation.py.

Every expected value below is hand-computed, not copy-pasted from the
implementation — that's the whole point of a ground-truth layer.
"""

from app.engine.reconciliation import compute_reconciliation
from app.models.billing import LineItem, Visit


def make_visit(
    visit_id="v1",
    payment_mode="cash",
    line_items=None,
    amount_paid_paise=0,
    discount_paise=0,
    is_refund=False,
    hour=10,
):
    return Visit(
        clinic_id="c1",
        visit_id=visit_id,
        timestamp=f"2026-07-27T{hour:02d}:00:00Z",
        doctor_id="d1",
        line_items=line_items or [],
        payment_mode=payment_mode,
        amount_paid_paise=amount_paid_paise,
        discount_paise=discount_paise,
        is_refund=is_refund,
    )


def test_single_fully_paid_visit():
    v = make_visit(
        line_items=[LineItem(drug_name="Paracetamol", qty=2, unit_price_paise=200)],
        payment_mode="cash",
        amount_paid_paise=400,
    )
    r = compute_reconciliation([v])
    assert r.total_billed_paise == 400
    assert r.total_collected_paise == 400
    assert r.outstanding_paise == 0
    assert r.refunds_paise == 0
    assert r.visit_count == 1
    assert r.outstanding_visit_count == 0


def test_partial_payment_creates_outstanding():
    v = make_visit(
        line_items=[LineItem(drug_name="Amoxicillin", qty=1, unit_price_paise=1000)],
        payment_mode="upi",
        amount_paid_paise=600,  # billed 1000, paid 600 -> 400 outstanding
    )
    r = compute_reconciliation([v])
    assert r.total_billed_paise == 1000
    assert r.total_collected_paise == 600
    assert r.outstanding_paise == 400
    assert r.outstanding_visit_count == 1


def test_refund_excluded_from_outstanding():
    """Core business rule: a refunded visit is closed/settled, never
    'outstanding' — even though billed(24000) != collected(-24000)."""
    v = make_visit(
        line_items=[LineItem(drug_name="Atorvastatin", qty=2, unit_price_paise=12000)],
        payment_mode="card",
        amount_paid_paise=-24000,
        is_refund=True,
    )
    r = compute_reconciliation([v])
    assert r.total_billed_paise == 24000
    assert r.total_collected_paise == -24000
    assert r.outstanding_paise == 0            # <- the key assertion
    assert r.refunds_paise == 24000
    assert r.refund_visit_count == 1
    assert r.outstanding_visit_count == 0


def test_mixed_day_matches_hand_computed_totals():
    """A day with a normal paid visit, a partial payment, and a refund —
    every number below was computed by hand, independently of the code."""
    visits = [
        make_visit(
            visit_id="v1", payment_mode="cash",
            line_items=[LineItem(drug_name="Paracetamol", qty=5, unit_price_paise=200)],
            amount_paid_paise=1000,  # fully paid: billed 1000, paid 1000
        ),
        make_visit(
            visit_id="v2", payment_mode="card",
            line_items=[LineItem(drug_name="Metformin", qty=3, unit_price_paise=3000)],
            amount_paid_paise=5000, discount_paise=1000,
            # billed = 9000 - 1000 = 8000; paid 5000 -> outstanding 3000
        ),
        make_visit(
            visit_id="v3", payment_mode="upi",
            line_items=[LineItem(drug_name="Omeprazole", qty=1, unit_price_paise=4000)],
            amount_paid_paise=-4000, is_refund=True,  # billed 4000, refunded fully
        ),
    ]
    r = compute_reconciliation(visits)

    assert r.total_billed_paise == 1000 + 8000 + 4000          # 13000
    assert r.total_collected_paise == 1000 + 5000 + -4000      # 2000
    assert r.outstanding_paise == 0 + 3000 + 0                 # 3000 (refund excluded)
    assert r.refunds_paise == 4000
    assert r.visit_count == 3
    assert r.refund_visit_count == 1
    assert r.outstanding_visit_count == 1

    assert r.by_payment_mode["cash"].billed_paise == 1000
    assert r.by_payment_mode["card"].billed_paise == 8000
    assert r.by_payment_mode["card"].outstanding_paise == 3000
    assert r.by_payment_mode["upi"].billed_paise == 4000
    assert r.by_payment_mode["upi"].outstanding_paise == 0


def test_empty_day_produces_zeroed_report_not_crash():
    r = compute_reconciliation([])
    assert r.total_billed_paise == 0
    assert r.total_collected_paise == 0
    assert r.outstanding_paise == 0
    assert r.refunds_paise == 0
    assert r.visit_count == 0
    assert r.by_payment_mode == {}