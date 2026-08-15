"""
Tests for app/ingestion/parser.py.

Covers the "non-happy-path day" the brief explicitly asks for: malformed
rows, duplicate visit_id, clinic_id mismatch, and non-dict rows — verifying
each produces a SPECIFIC error (row_index + field + reason), not a crash.
"""

from app.ingestion.parser import parse_billing_log

GOOD_ROW = {
    "clinic_id": "mehta-clinic",
    "visit_id": "v1",
    "timestamp": "2026-07-27T10:00:00Z",
    "doctor_id": "doc-1",
    "line_items": [{"drug_name": "Paracetamol", "qty": 2, "unit_price_paise": 200}],
    "payment_mode": "cash",
    "is_refund": False,
    "amount_paid_paise": 400,
    "discount_paise": 0,
}


def make_row(**overrides):
    row = dict(GOOD_ROW)
    row.update(overrides)
    return row


def test_all_valid_rows_parse_cleanly():
    rows = [make_row(visit_id="v1"), make_row(visit_id="v2")]
    result = parse_billing_log(rows)
    assert result.valid_count == 2
    assert result.rejected_count == 0
    assert result.total_rows == 2


def test_missing_required_field_is_row_error_not_crash():
    bad_row = dict(GOOD_ROW)
    del bad_row["payment_mode"]
    result = parse_billing_log([bad_row])
    assert result.valid_count == 0
    assert result.rejected_count == 1
    assert result.errors[0].row_index == 0
    assert any(issue.field == "payment_mode" for issue in result.errors[0].issues)


def test_invalid_enum_payment_mode_is_specific_error():
    bad_row = make_row(payment_mode="bitcoin")
    result = parse_billing_log([bad_row])
    assert result.rejected_count == 1
    assert any(issue.field == "payment_mode" for issue in result.errors[0].issues)


def test_negative_qty_line_item_rejected():
    bad_row = make_row(line_items=[{"drug_name": "X", "qty": -3, "unit_price_paise": 100}])
    result = parse_billing_log([bad_row])
    assert result.rejected_count == 1
    assert "line_items" in result.errors[0].issues[0].field


def test_refund_sign_mismatch_rejected():
    bad_row = make_row(is_refund=True, amount_paid_paise=500)  # should be <= 0
    result = parse_billing_log([bad_row])
    assert result.rejected_count == 1


def test_non_dict_row_handled_gracefully_not_a_crash():
    rows = ["this is not a row", 12345, None]
    result = parse_billing_log(rows)
    assert result.valid_count == 0
    assert result.rejected_count == 3
    for err in result.errors:
        assert "expected a JSON object" in err.issues[0].reason


def test_duplicate_visit_id_keeps_first_flags_second():
    rows = [make_row(visit_id="dup"), make_row(visit_id="dup")]
    result = parse_billing_log(rows)
    assert result.valid_count == 1
    assert result.rejected_count == 1
    assert result.errors[0].row_index == 1
    assert "duplicate visit_id" in result.errors[0].issues[0].reason


def test_clinic_id_mismatch_flagged():
    rows = [
        make_row(visit_id="v1", clinic_id="mehta-clinic"),
        make_row(visit_id="v2", clinic_id="some-other-clinic"),
    ]
    result = parse_billing_log(rows)
    assert result.valid_count == 1
    assert result.rejected_count == 1
    assert "clinic_id" in result.errors[0].issues[0].field


def test_mixed_good_and_bad_rows_partial_success():
    """A file with 2 good rows and 1 bad row ingests the 2 good ones —
    we don't reject the whole file for one bad row."""
    rows = [
        make_row(visit_id="v1"),
        make_row(visit_id="v2", payment_mode="invalid_mode"),
        make_row(visit_id="v3"),
    ]
    result = parse_billing_log(rows)
    assert result.total_rows == 3
    assert result.valid_count == 2
    assert result.rejected_count == 1
    assert result.errors[0].row_index == 1


def test_empty_log_does_not_crash():
    result = parse_billing_log([])
    assert result.total_rows == 0
    assert result.valid_count == 0
    assert result.rejected_count == 0


def test_errors_sorted_by_row_index():
    """Cross-row errors (pass 2) can be appended out of order relative to
    per-row errors (pass 1) — verify the final list is still sorted."""
    rows = [
        make_row(visit_id="v1"),
        make_row(visit_id="v1"),              # duplicate -> pass 2 error, row 1
        make_row(payment_mode="bad"),          # pass 1 error, row 2
    ]
    result = parse_billing_log(rows)
    indices = [e.row_index for e in result.errors]
    assert indices == sorted(indices)