"""
Parses a raw billing log (list of dicts, e.g. from an uploaded JSON file)
into validated Visit objects, collecting per-row errors instead of failing
the whole file on the first bad row.

Design decisions:
  - PARTIAL SUCCESS MODEL: a file with 17 good rows and 1 bad row ingests
    the 17 good ones and reports the 1 bad one with row_index/field/reason.
    We do NOT reject the whole file for one bad row — more realistic for
    a clinic's front desk, and gives the API something useful to show.
  - DUPLICATE visit_id: schema says visit_id is "unique per visit". If two
    rows share a visit_id, we keep the FIRST occurrence as valid and flag
    every subsequent occurrence as a row error. (Documented assumption —
    revisit if real sample data shows a different intended behavior.)
  - CLINIC MISMATCH: schema says "single clinic per file". The first valid
    row's clinic_id is treated as the file's clinic_id; any row with a
    different clinic_id is flagged as a row error, not silently merged in.
  - NON-DICT ROWS: if a "row" isn't even a JSON object (e.g. a bare string
    or number in the array), we catch that explicitly rather than letting
    an AttributeError/TypeError propagate as a 500.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.ingestion.errors import FieldIssue, ParseResult, RowError
from app.models.billing import Visit


def _validation_error_to_issues(exc: ValidationError) -> list[FieldIssue]:
    issues = []
    for err in exc.errors():
        field_path = ".".join(str(loc) for loc in err["loc"]) or "(row)"
        issues.append(FieldIssue(field=field_path, reason=err["msg"]))
    return issues


def parse_billing_log(raw_rows: list[Any]) -> ParseResult:
    """
    Parse a raw billing log into validated Visits + a list of row errors.
    Never raises — always returns a ParseResult, even for a fully empty
    or fully malformed input. Callers (e.g. the future API layer) decide
    what HTTP status/response shape to build from this.
    """
    candidate_visits: list[tuple[int, Visit]] = []
    errors: list[RowError] = []

    # --- Pass 1: per-row structural + field validation ---
    for idx, raw_row in enumerate(raw_rows):
        if not isinstance(raw_row, dict):
            errors.append(
                RowError(
                    row_index=idx,
                    issues=[FieldIssue(
                        field="(row)",
                        reason=f"expected a JSON object, got {type(raw_row).__name__}",
                    )],
                    raw_row={"__invalid_row__": repr(raw_row)},
                )
            )
            continue

        try:
            visit = Visit(**raw_row)
            candidate_visits.append((idx, visit))
        except ValidationError as exc:
            errors.append(
                RowError(
                    row_index=idx,
                    issues=_validation_error_to_issues(exc),
                    raw_row=raw_row,
                )
            )

    # --- Pass 2: cross-row checks (duplicates, clinic consistency) ---
    seen_visit_ids: dict[str, int] = {}  # visit_id -> first row_index that used it
    expected_clinic_id: str | None = None
    final_valid: list[Visit] = []

    for idx, visit in candidate_visits:
        if expected_clinic_id is None:
            expected_clinic_id = visit.clinic_id

        if visit.clinic_id != expected_clinic_id:
            errors.append(
                RowError(
                    row_index=idx,
                    issues=[FieldIssue(
                        field="clinic_id",
                        reason=(
                            f"clinic_id '{visit.clinic_id}' does not match this "
                            f"file's clinic_id '{expected_clinic_id}' "
                            "(schema requires a single clinic per file)"
                        ),
                    )],
                    raw_row=visit.model_dump(mode="json"),
                )
            )
            continue

        if visit.visit_id in seen_visit_ids:
            first_idx = seen_visit_ids[visit.visit_id]
            errors.append(
                RowError(
                    row_index=idx,
                    issues=[FieldIssue(
                        field="visit_id",
                        reason=(
                            f"duplicate visit_id '{visit.visit_id}', "
                            f"first seen at row_index {first_idx}"
                        ),
                    )],
                    raw_row=visit.model_dump(mode="json"),
                )
            )
            continue

        seen_visit_ids[visit.visit_id] = idx
        final_valid.append(visit)

    # Row errors aren't guaranteed to come out in row_index order (pass 2
    # can append after pass 1 finished) — sort for a predictable, readable
    # API response.
    errors.sort(key=lambda e: e.row_index)

    return ParseResult(
        valid_visits=final_valid,
        errors=errors,
        total_rows=len(raw_rows),
        valid_count=len(final_valid),
        rejected_count=len(errors),
    )