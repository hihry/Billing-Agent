"""
Structured error types for billing log ingestion.

Why this file exists separately from parser.py:
These shapes are the CONTRACT between ingestion and the future API layer.
When Step 5 wires POST /api/logs, it will serialize a list of these
directly into the 422 response body. Getting the shape right here means
zero rework later — "specific, actionable error, not a generic 500"
literally means: row index + field + human-readable reason, always.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.models.billing import Visit


class FieldIssue(BaseModel):
    """One specific thing wrong with one field in one row."""
    field: str
    reason: str


class RowError(BaseModel):
    """
    Everything wrong with a single row, plus enough context (row_index,
    raw_row) that a clinic's front-desk operator could actually go fix
    their source data — not just see 'validation failed'.
    """
    row_index: int
    issues: list[FieldIssue]
    raw_row: dict


class ParseResult(BaseModel):
    """
    Outcome of parsing an entire billing log file.

    valid_visits stays as REAL Visit objects, not dicts — the engine
    (Step 3) needs typed objects to do arithmetic on. Only the API layer
    (Step 5) should flatten these to dicts/JSON, at the HTTP boundary,
    not here. Keeping this distinction now avoids a rework later.
    """
    valid_visits: list[Visit]
    errors: list[RowError]
    total_rows: int
    valid_count: int
    rejected_count: int