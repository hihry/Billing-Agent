"""
Tests using REAL sample data provided by SwasthiQ, not synthetic fixtures.

billing_log_2026-07-25.json is a genuine edge case: every single visit that
day is a refund (is_refund=True for all 3 rows). This locks in a deliberate
design decision made while reviewing this file:

  A refunded visit still counts toward total_billed. Billing is a
  historical fact ("a bill WAS raised"); a refund is a separate,
  independent event layered on top, not a rewrite of history. This means
  total_collected CAN legitimately go negative on a day like this one —
  and that's correct, not a bug. The four dashboard stats (billed,
  collected, outstanding, refunds) are independent numbers, not derived
  from one another, matching how the mockup presents them as four
  separate stat cards.

  Separately: outstanding_paise must be 0 on this day (refunds are never
  "outstanding"), and the Analytics report must be entirely empty (no
  revenue, no medicines, peak_hour=None) since analytics excludes refund
  line items — this day had zero genuine sales.

The reconciliation and analytics engines (Step 3) must satisfy this test.
"""

import json
from pathlib import Path

from app.engine.analytics import compute_analytics
from app.engine.reconciliation import compute_reconciliation
from app.ingestion.parser import parse_billing_log

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(filename: str) -> list[dict]:
    with open(FIXTURES_DIR / filename) as f:
        return json.load(f)


def test_july25_all_rows_parse_valid():
    """Sanity check: this real file should parse with zero errors —
    it's clean data from SwasthiQ, not a malformed-row test case."""
    rows = load_fixture("billing_log_2026-07-25.json")
    result = parse_billing_log(rows)
    assert result.total_rows == 3
    assert result.valid_count == 3
    assert result.rejected_count == 0


def test_july25_is_an_all_refunds_day():
    """Every visit this day is a refund — this is the edge case itself."""
    rows = load_fixture("billing_log_2026-07-25.json")
    result = parse_billing_log(rows)
    assert all(v.is_refund for v in result.valid_visits)


def test_july25_billed_totals_despite_all_refunds():
    """A refunded visit still contributes to billed_paise (computed from
    line items), even though amount_paid_paise is negative. This is the
    decision we made explicitly, not by accident."""
    rows = load_fixture("billing_log_2026-07-25.json")
    result = parse_billing_log(rows)

    total_billed = sum(v.billed_paise for v in result.valid_visits)
    total_collected = sum(v.amount_paid_paise for v in result.valid_visits)

    # 2*12000 (atorvastatin) + (3*6000 + 1*4000) (amox+omeprazole) + 1*3000 (metformin)
    assert total_billed == 24000 + 22000 + 3000  # = 49000 paise = ₹490
    # sum of the negative amount_paid_paise values
    assert total_collected == -24000 + -22000 + -3000  # = -49000 paise

    # The key assertion: collected is allowed to be NEGATIVE. This is not
    # a bug to guard against — it's the correct behavior for an all-refund day.
    assert total_collected < 0
    assert total_collected != total_billed


def test_july25_reconciliation_end_to_end():
    """Full pipeline: parse -> reconciliation engine, using the real file."""
    rows = load_fixture("billing_log_2026-07-25.json")
    visits = parse_billing_log(rows).valid_visits
    r = compute_reconciliation(visits)

    assert r.total_billed_paise == 49000
    assert r.total_collected_paise == -49000
    assert r.outstanding_paise == 0          # refunds are never outstanding
    assert r.refunds_paise == 49000
    assert r.visit_count == 3
    assert r.refund_visit_count == 3
    assert r.outstanding_visit_count == 0

    # single payment mode per visit, mixed modes across the 3 refunds
    assert set(r.by_payment_mode.keys()) == {"card", "upi"}
    assert r.by_payment_mode["upi"].billed_paise == 22000 + 3000  # v2 + v3


def test_july25_analytics_end_to_end_is_empty():
    """Full pipeline: parse -> analytics engine. Since every visit is a
    refund, analytics must be entirely empty — not an error, not stale
    data leaking in, genuinely empty."""
    rows = load_fixture("billing_log_2026-07-25.json")
    visits = parse_billing_log(rows).valid_visits
    a = compute_analytics(visits)

    assert a.revenue_by_hour == []
    assert a.peak_hour is None
    assert a.peak_hour_revenue_paise is None
    assert a.top_medicines_by_qty == []
    assert a.top_medicines_by_revenue == []