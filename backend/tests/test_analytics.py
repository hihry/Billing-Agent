"""
Tests for app/engine/analytics.py.
"""

from app.engine.analytics import compute_analytics
from app.models.billing import LineItem, Visit


def make_visit(visit_id="v1", hour=10, line_items=None, is_refund=False, amount_paid_paise=0):
    return Visit(
        clinic_id="c1",
        visit_id=visit_id,
        timestamp=f"2026-07-27T{hour:02d}:00:00Z",
        doctor_id="d1",
        line_items=line_items or [],
        payment_mode="cash",
        amount_paid_paise=amount_paid_paise,
        is_refund=is_refund,
    )


def test_revenue_by_hour_and_peak_hour():
    visits = [
        make_visit("v1", hour=9, line_items=[LineItem(drug_name="A", qty=1, unit_price_paise=1000)],
                    amount_paid_paise=1000),
        make_visit("v2", hour=12, line_items=[LineItem(drug_name="B", qty=1, unit_price_paise=5000)],
                    amount_paid_paise=5000),
        make_visit("v3", hour=12, line_items=[LineItem(drug_name="C", qty=1, unit_price_paise=3400)],
                    amount_paid_paise=3400),
    ]
    a = compute_analytics(visits)
    by_hour = {h.hour: h.revenue_paise for h in a.revenue_by_hour}
    assert by_hour == {9: 1000, 12: 8400}
    assert a.peak_hour == 12
    assert a.peak_hour_revenue_paise == 8400


def test_refund_visits_excluded_from_analytics():
    """Core business rule: a refund's line items didn't move product out
    the door today — they reverse a past sale, so they're excluded from
    revenue-by-hour and medicine rankings entirely."""
    visits = [
        make_visit("v1", hour=10, line_items=[LineItem(drug_name="Paracetamol", qty=5, unit_price_paise=200)],
                    amount_paid_paise=1000),
        make_visit("v2", hour=11, line_items=[LineItem(drug_name="Atorvastatin", qty=2, unit_price_paise=12000)],
                    amount_paid_paise=-24000, is_refund=True),
    ]
    a = compute_analytics(visits)
    drug_names_in_qty = {m.drug_name for m in a.top_medicines_by_qty}
    assert "Atorvastatin" not in drug_names_in_qty
    assert "Paracetamol" in drug_names_in_qty
    assert a.peak_hour == 10  # not 11, since the refund hour contributes 0


def test_all_refund_day_gives_empty_analytics_not_crash():
    """Matches the REAL July 25 sample file: every visit is a refund.
    Analytics should be empty/None, not an error."""
    visits = [
        make_visit("v1", hour=10, line_items=[LineItem(drug_name="X", qty=1, unit_price_paise=100)],
                    amount_paid_paise=-100, is_refund=True),
    ]
    a = compute_analytics(visits)
    assert a.revenue_by_hour == []
    assert a.peak_hour is None
    assert a.peak_hour_revenue_paise is None
    assert a.top_medicines_by_qty == []
    assert a.top_medicines_by_revenue == []


def test_top_medicines_by_qty_and_revenue_are_distinct_rankings():
    """A drug can rank high by quantity but low by revenue (cheap, bulk)
    and vice versa (expensive, rarely bought) — the two rankings must be
    genuinely independent, not the same list reordered."""
    visits = [
        make_visit("v1", line_items=[
            LineItem(drug_name="Cheap_HighQty", qty=100, unit_price_paise=10),   # revenue 1000
            LineItem(drug_name="Expensive_LowQty", qty=2, unit_price_paise=5000),  # revenue 10000
        ], amount_paid_paise=11000),
    ]
    a = compute_analytics(visits)
    assert a.top_medicines_by_qty[0].drug_name == "Cheap_HighQty"
    assert a.top_medicines_by_revenue[0].drug_name == "Expensive_LowQty"


def test_tie_break_is_alphabetical_and_deterministic():
    visits = [
        make_visit("v1", line_items=[
            LineItem(drug_name="Zinc", qty=5, unit_price_paise=100),
            LineItem(drug_name="Amoxicillin", qty=5, unit_price_paise=100),  # same qty, same revenue
        ], amount_paid_paise=1000),
    ]
    a = compute_analytics(visits)
    assert a.top_medicines_by_qty[0].drug_name == "Amoxicillin"  # alphabetically first
    assert a.top_medicines_by_revenue[0].drug_name == "Amoxicillin"


def test_top_n_caps_at_five():
    line_items = [
        LineItem(drug_name=f"Drug{i}", qty=10 - i, unit_price_paise=100) for i in range(8)
    ]
    visits = [make_visit("v1", line_items=line_items, amount_paid_paise=100)]
    a = compute_analytics(visits)
    assert len(a.top_medicines_by_qty) == 5
    assert len(a.top_medicines_by_revenue) == 5


def test_empty_visits_list_does_not_crash():
    a = compute_analytics([])
    assert a.revenue_by_hour == []
    assert a.peak_hour is None