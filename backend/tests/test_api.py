"""
Integration tests for the full API: request -> parser -> engine -> SQLite
-> response. Each test gets a FRESH in-memory database via create_app(":memory:")
so tests never leak state into each other.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

FIXTURES_DIR = Path(__file__).parent / "fixtures"

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


@pytest.fixture
def client():
    app = create_app(":memory:")
    with TestClient(app) as c:
        yield c


def test_ingest_all_valid_rows_returns_201(client):
    rows = [make_row(visit_id="v1"), make_row(visit_id="v2")]
    resp = client.post("/api/logs", json=rows)
    assert resp.status_code == 201
    body = resp.json()
    assert body["valid_count"] == 2
    assert body["rejected_count"] == 0
    assert body["errors"] == []
    assert body["log_id"] == "mehta-clinic-2026-07-27"


def test_ingest_all_malformed_rows_returns_422_not_500(client):
    bad_row = make_row(payment_mode="bitcoin")
    resp = client.post("/api/logs", json=[bad_row])
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"] == "no_valid_rows"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["row_index"] == 0
    assert any(issue["field"] == "payment_mode" for issue in body["errors"][0]["issues"])


def test_ingest_partial_success_still_201_with_errors_listed(client):
    rows = [make_row(visit_id="v1"), make_row(visit_id="v2", payment_mode="bad_mode")]
    resp = client.post("/api/logs", json=rows)
    assert resp.status_code == 201
    body = resp.json()
    assert body["valid_count"] == 1
    assert body["rejected_count"] == 1
    assert len(body["errors"]) == 1


def test_get_logs_lists_ingested_log(client):
    client.post("/api/logs", json=[make_row(visit_id="v1")])
    resp = client.get("/api/logs")
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) == 1
    assert logs[0]["clinic_id"] == "mehta-clinic"
    assert logs[0]["visit_count"] == 1


def test_reconciliation_endpoint_matches_engine_computation(client):
    rows = [
        make_row(visit_id="v1", amount_paid_paise=400,
                  line_items=[{"drug_name": "Paracetamol", "qty": 2, "unit_price_paise": 200}]),
    ]
    ingest_resp = client.post("/api/logs", json=rows)
    log_id = ingest_resp.json()["log_id"]

    resp = client.get(f"/api/logs/{log_id}/reconciliation")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_billed_paise"] == 400
    assert body["total_collected_paise"] == 400
    assert body["outstanding_paise"] == 0


def test_analytics_endpoint_returns_correct_peak_hour(client):
    rows = [
        make_row(visit_id="v1", timestamp="2026-07-27T09:00:00Z", amount_paid_paise=200,
                  line_items=[{"drug_name": "A", "qty": 1, "unit_price_paise": 200}]),
        make_row(visit_id="v2", timestamp="2026-07-27T12:00:00Z", amount_paid_paise=1000,
                  line_items=[{"drug_name": "B", "qty": 1, "unit_price_paise": 1000}]),
    ]
    ingest_resp = client.post("/api/logs", json=rows)
    log_id = ingest_resp.json()["log_id"]

    resp = client.get(f"/api/logs/{log_id}/analytics")
    assert resp.status_code == 200
    body = resp.json()
    assert body["peak_hour"] == 12
    assert body["peak_hour_revenue_paise"] == 1000


def test_reconciliation_for_nonexistent_log_is_404_not_500(client):
    resp = client.get("/api/logs/does-not-exist/reconciliation")
    assert resp.status_code == 404
    assert "does-not-exist" in resp.json()["detail"]


def test_analytics_for_nonexistent_log_is_404_not_500(client):
    resp = client.get("/api/logs/does-not-exist/analytics")
    assert resp.status_code == 404


def test_reupload_same_clinic_day_upserts_not_duplicates(client):
    """The core 'data consistency upon update' guarantee: re-ingesting the
    same clinic-day replaces the old data instead of duplicating it."""
    first_rows = [make_row(visit_id="v1", amount_paid_paise=400)]
    resp1 = client.post("/api/logs", json=first_rows)
    log_id = resp1.json()["log_id"]
    assert resp1.json()["valid_count"] == 1

    # Re-upload the SAME clinic-day with DIFFERENT (corrected) data —
    # 3 visits this time instead of 1.
    second_rows = [
        make_row(visit_id="v1", amount_paid_paise=400),
        make_row(visit_id="v2", amount_paid_paise=600),
        make_row(visit_id="v3", amount_paid_paise=800),
    ]
    resp2 = client.post("/api/logs", json=second_rows)
    assert resp2.json()["log_id"] == log_id  # same log_id, deterministic
    assert resp2.json()["valid_count"] == 3

    # GET /api/logs should show ONE log entry with the NEW visit count —
    # not two entries, and not a stale count from the first upload.
    logs = client.get("/api/logs").json()
    assert len(logs) == 1
    assert logs[0]["visit_count"] == 3

    # Reconciliation should reflect ONLY the new data (400+600+800=1800),
    # not old+new combined (which would indicate a consistency bug).
    recon = client.get(f"/api/logs/{log_id}/reconciliation").json()
    assert recon["total_collected_paise"] == 1800
    assert recon["visit_count"] == 3


def test_july25_real_file_end_to_end_through_api(client):
    """The real SwasthiQ sample file (all refunds), through the full
    HTTP API, not just the engine functions directly."""
    with open(FIXTURES_DIR / "billing_log_2026-07-25.json") as f:
        rows = json.load(f)

    resp = client.post("/api/logs", json=rows)
    assert resp.status_code == 201
    body = resp.json()
    assert body["valid_count"] == 3
    assert body["rejected_count"] == 0
    log_id = body["log_id"]

    recon = client.get(f"/api/logs/{log_id}/reconciliation").json()
    assert recon["total_billed_paise"] == 49000
    assert recon["total_collected_paise"] == -49000
    assert recon["outstanding_paise"] == 0
    assert recon["refunds_paise"] == 49000

    analytics = client.get(f"/api/logs/{log_id}/analytics").json()
    assert analytics["revenue_by_hour"] == []
    assert analytics["peak_hour"] is None