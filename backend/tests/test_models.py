"""
Tests for the core Pydantic models (app/models/billing.py).

These exist mainly to lock in one subtle bug we hit while building this:
Pydantic v2 cross-field validators can only see fields defined BEFORE
the field being validated. `is_refund` must stay defined before
`amount_paid_paise` in the Visit model, or refund_sign_consistency()
silently breaks (accepts what it should reject, rejects what it should
accept). test_refund_sign_consistency_field_order_regression guards this.
"""

import pytest
from pydantic import ValidationError

from app.models.billing import LineItem, Visit

BASE_VISIT_KWARGS = dict(
    clinic_id="clinic-1",
    visit_id="visit-1",
    timestamp="2026-07-27T10:00:00Z",
    doctor_id="doc-1",
    payment_mode="cash",
)  # line_items intentionally omitted here — defaults to [] via the model,
   # and tests that care about line_items pass it explicitly to avoid
   # "got multiple values for keyword argument" collisions.


def test_valid_refund_accepted():
    v = Visit(**BASE_VISIT_KWARGS, amount_paid_paise=-500, is_refund=True)
    assert v.amount_paid_paise == -500


def test_valid_normal_payment_accepted():
    v = Visit(**BASE_VISIT_KWARGS, amount_paid_paise=500, is_refund=False)
    assert v.amount_paid_paise == 500


def test_refund_sign_consistency_field_order_regression():
    """The bug we caught: is_refund must be validated before amount_paid_paise."""
    # positive amount claiming to be a refund -> reject
    with pytest.raises(ValidationError):
        Visit(**BASE_VISIT_KWARGS, amount_paid_paise=500, is_refund=True)
    # negative amount NOT flagged as a refund -> reject
    with pytest.raises(ValidationError):
        Visit(**BASE_VISIT_KWARGS, amount_paid_paise=-500, is_refund=False)


def test_line_item_qty_zero_rejected():
    with pytest.raises(ValidationError):
        LineItem(drug_name="Paracetamol", qty=0, unit_price_paise=200)


def test_line_item_qty_negative_rejected():
    with pytest.raises(ValidationError):
        LineItem(drug_name="Paracetamol", qty=-3, unit_price_paise=200)


def test_line_item_negative_price_rejected():
    with pytest.raises(ValidationError):
        LineItem(drug_name="Paracetamol", qty=1, unit_price_paise=-1)


def test_line_item_blank_drug_name_rejected():
    with pytest.raises(ValidationError):
        LineItem(drug_name="   ", qty=1, unit_price_paise=200)


def test_discount_negative_rejected():
    with pytest.raises(ValidationError):
        Visit(**BASE_VISIT_KWARGS, amount_paid_paise=500, discount_paise=-100)


def test_billed_paise_applies_discount():
    v = Visit(
        **BASE_VISIT_KWARGS,
        line_items=[LineItem(drug_name="Paracetamol", qty=10, unit_price_paise=200)],
        amount_paid_paise=1800,
        discount_paise=200,
    )
    assert v.billed_paise == 1800  # (10 * 200) - 200


def test_billed_paise_floors_at_zero_when_discount_exceeds_subtotal():
    v = Visit(
        **BASE_VISIT_KWARGS,
        line_items=[LineItem(drug_name="Paracetamol", qty=1, unit_price_paise=100)],
        amount_paid_paise=0,
        discount_paise=500,  # bigger than the 100 paise subtotal
    )
    assert v.billed_paise == 0


def test_billed_paise_with_no_line_items_is_zero():
    """Consultation-only visit with no medicines: billed-from-items is 0.
    (Documented assumption: consultation fee, if any, lives in amount_paid_paise,
    not modeled as a separate field in this schema.)"""
    v = Visit(**BASE_VISIT_KWARGS, line_items=[], amount_paid_paise=300)
    assert v.billed_paise == 0