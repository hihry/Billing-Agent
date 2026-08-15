"""
Core data models for the billing log.

These models are the single source of truth for what a "valid row" means.
Every validation rule lives HERE, not scattered across parsing code —
so the parser's job becomes simple: "try to build a Visit, catch what fails."

Design decisions (documented here so the reasoning travels with the code):
  - Money is stored as integer paise throughout, never float rupees.
    Floats introduce rounding drift that would break exact-match checks
    later (e.g. the LLM grounding validator diffs numbers exactly).
  - qty must be a strictly positive integer. Negative-money situations
    have exactly one sanctioned path: `is_refund=True` at the visit level.
    We deliberately do NOT support negative qty as a second way to express
    the same concept — one mechanism per concept avoids ambiguous totals.
  - unit_price_paise >= 0. Free samples (0) are plausible; negative prices
    are not something the schema describes, so they're rejected.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class PaymentMode(str, Enum):
    cash = "cash"
    card = "card"
    upi = "upi"


class LineItem(BaseModel):
    drug_name: str = Field(min_length=1)
    qty: int = Field(gt=0, description="Strictly positive. Refunds are handled at visit level.")
    unit_price_paise: int = Field(ge=0)

    @field_validator("drug_name")
    @classmethod
    def strip_and_validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("drug_name cannot be blank/whitespace-only")
        return v


class Visit(BaseModel):
    clinic_id: str = Field(min_length=1)
    visit_id: str = Field(min_length=1)
    timestamp: datetime  # ISO 8601, expected UTC per schema
    doctor_id: str = Field(min_length=1)
    line_items: list[LineItem] = Field(default_factory=list)
    payment_mode: PaymentMode
    is_refund: bool = False  # MUST be defined before amount_paid_paise (see validator below)
    amount_paid_paise: int
    discount_paise: int = 0

    @field_validator("discount_paise")
    @classmethod
    def discount_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("discount_paise cannot be negative")
        return v

    @field_validator("amount_paid_paise")
    @classmethod
    def refund_sign_consistency(cls, v: int, info) -> int:
        # Cross-field check: if is_refund is True, amount_paid_paise must be <= 0.
        # If is_refund is False, amount_paid_paise must be >= 0.
        # NOTE: field order matters for pydantic v2 cross-field validation —
        # is_refund must be defined BEFORE amount_paid_paise for info.data
        # to contain it. We validate this ordering with a test.
        is_refund = info.data.get("is_refund", False)
        if is_refund and v > 0:
            raise ValueError(
                "is_refund=True requires amount_paid_paise <= 0 "
                f"(got {v}, a positive amount cannot be a refund)"
            )
        if not is_refund and v < 0:
            raise ValueError(
                "amount_paid_paise cannot be negative unless is_refund=True "
                f"(got {v} with is_refund=False)"
            )
        return v

    @property
    def billed_paise(self) -> int:
        """What SHOULD have been paid for this visit, before collection."""
        subtotal = sum(li.qty * li.unit_price_paise for li in self.line_items)
        return max(subtotal - self.discount_paise, 0)