"""
API routes. Each endpoint is deliberately thin — it orchestrates calls to
ingestion/engine/storage, but contains no business logic itself. If you're
tempted to compute something here, it belongs in app/engine/ instead.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response, status

from app.api.schemas import IngestAllRowsRejectedResponse, IngestLogResponse, LogSummary
from app.engine.analytics import compute_analytics
from app.engine.reconciliation import compute_reconciliation
from app.ingestion.parser import parse_billing_log
from app.models.reports import AnalyticsReport, ReconciliationReport
from app.storage.repository import LogRepository

router = APIRouter(prefix="/api")


def get_repository(request: Request) -> LogRepository:
    return request.app.state.repository


@router.post(
    "/logs",
    response_model=IngestLogResponse | IngestAllRowsRejectedResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_log(rows: list[dict[str, Any]], request: Request, response: Response):
    repo = get_repository(request)

    parse_result = parse_billing_log(rows)

    if parse_result.valid_count == 0:
        # Nothing valid to store. This is the one case that returns a
        # non-201 status — everything else (including partial success)
        # is a 201 with an `errors` array attached.
        response.status_code = 422
        return IngestAllRowsRejectedResponse(
            total_rows=parse_result.total_rows,
            errors=parse_result.errors,
        )

    reconciliation = compute_reconciliation(parse_result.valid_visits)
    analytics = compute_analytics(parse_result.valid_visits)

    log_id, clinic_id, log_date = repo.upsert_log(
        visits=parse_result.valid_visits,
        total_rows=parse_result.total_rows,
        rejected_count=parse_result.rejected_count,
    )
    repo.save_reports_cache(log_id, reconciliation, analytics)

    return IngestLogResponse(
        log_id=log_id,
        clinic_id=clinic_id,
        log_date=log_date,
        total_rows=parse_result.total_rows,
        valid_count=parse_result.valid_count,
        rejected_count=parse_result.rejected_count,
        errors=parse_result.errors,
    )


@router.get("/logs", response_model=list[LogSummary])
def list_logs(request: Request):
    repo = get_repository(request)
    rows = repo.list_logs()
    return [
        LogSummary(
            log_id=r["log_id"],
            clinic_id=r["clinic_id"],
            log_date=r["log_date"],
            visit_count=r["valid_count"],
            rejected_count=r["rejected_count"],
            uploaded_at=r["uploaded_at"],
        )
        for r in rows
    ]


@router.get("/logs/{log_id}/reconciliation", response_model=ReconciliationReport)
def get_reconciliation(log_id: str, request: Request):
    repo = get_repository(request)
    return repo.get_cached_reconciliation(log_id)  # raises 404 internally if missing


@router.get("/logs/{log_id}/analytics", response_model=AnalyticsReport)
def get_analytics(log_id: str, request: Request):
    repo = get_repository(request)
    return repo.get_cached_analytics(log_id)  # raises 404 internally if missing