"""
API-facing schemas — the exact JSON shapes clients see. Kept separate from
the internal engine/storage models so the API contract can stay stable
even if internal representations change later.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.ingestion.errors import RowError
from app.narrative.schemas import CitedFigure


class LogSummary(BaseModel):
    """One row in GET /api/logs — lightweight, for the sidebar."""
    log_id: str
    clinic_id: str
    log_date: str
    visit_count: int
    rejected_count: int
    uploaded_at: str


class IngestLogResponse(BaseModel):
    """Response for POST /api/logs. Returned even on PARTIAL success
    (some rows rejected) — the errors list is always present, empty or not."""
    log_id: str
    clinic_id: str
    log_date: str
    total_rows: int
    valid_count: int
    rejected_count: int
    errors: list[RowError]


class IngestAllRowsRejectedResponse(BaseModel):
    """Response body for the 422 case: every row in the file was
    malformed, so there's nothing to store. Distinct shape from
    IngestLogResponse because there's no log_id to report."""
    error: str = "no_valid_rows"
    total_rows: int
    errors: list[RowError]


class NarrativeResponse(BaseModel):
    log_id: str
    narrative: str
    cited_figures: list[CitedFigure]
    grounding_status: str
    generated_at: str