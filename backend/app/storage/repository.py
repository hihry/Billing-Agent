"""
Repository layer — the ONLY place that writes raw SQL. Everything else in
the app talks to this in terms of Visit / ReconciliationReport / etc.

=== The "data consistency upon update" story (README-worthy) ===

log_id is DETERMINISTIC: f"{clinic_id}-{log_date}". This means re-ingesting
the same clinic-day (e.g. the clinic front desk re-sends a corrected file)
naturally maps to the SAME log_id — it's an upsert, not a duplicate insert.

upsert_log() wraps its DELETE-then-INSERT sequence in a single SQLite
transaction using `with self.db.conn:` (Python's sqlite3 context-manager
idiom: commits on clean exit, ROLLS BACK on any exception). This matters
because the write touches 3 tables (billing_logs, visits, line_items) and
a partial failure partway through — say, the process crashes after
deleting old visits but before inserting all the new ones — would leave
the log in a corrupted, half-written state if each statement committed
independently. Wrapping the whole sequence in one transaction means the
old data is preserved untouched unless the ENTIRE new write succeeds.
Consistency is guaranteed by atomicity, not by careful ordering of steps.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import HTTPException

from app.ingestion.errors import RowError
from app.models.billing import LineItem, PaymentMode, Visit
from app.models.reports import AnalyticsReport, ReconciliationReport
from app.narrative.schemas import CitedFigure, NarrativeContent
from app.storage.db import Database


class LogRepository:
    def __init__(self, db: Database):
        self.db = db

    # ---------- writes ----------

    def upsert_log(
        self, visits: list[Visit], total_rows: int, rejected_count: int
    ) -> tuple[str, str, str]:
        """
        Ingest (or re-ingest) one clinic-day's worth of visits.
        Returns (log_id, clinic_id, log_date_iso). Raises ValueError if
        `visits` is empty — an empty log is a caller error, handled at
        the API layer as a 422, never silently stored.
        """
        if not visits:
            raise ValueError("Cannot upsert a log with zero valid visits")

        clinic_id = visits[0].clinic_id  # parser guarantees single clinic_id among valid visits
        log_date = min(v.timestamp for v in visits).date()
        log_id = f"{clinic_id}-{log_date.isoformat()}"
        now = datetime.now(timezone.utc).isoformat()

        with self.db.conn:  # atomic: commits on success, rolls back on any exception
            # Upsert semantics: wipe any previous rows for this log_id
            # BEFORE inserting the new set, all inside the same transaction,
            # so a re-upload never leaves stale/duplicated visits behind.
            self.db.conn.execute(
                "DELETE FROM line_items WHERE visit_row_id IN "
                "(SELECT id FROM visits WHERE log_id = ?)",
                (log_id,),
            )
            self.db.conn.execute("DELETE FROM visits WHERE log_id = ?", (log_id,))
            self.db.conn.execute("DELETE FROM reports_cache WHERE log_id = ?", (log_id,))

            self.db.conn.execute(
                """
                INSERT INTO billing_logs
                    (log_id, clinic_id, log_date, uploaded_at, total_rows, valid_count, rejected_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(log_id) DO UPDATE SET
                    uploaded_at = excluded.uploaded_at,
                    total_rows = excluded.total_rows,
                    valid_count = excluded.valid_count,
                    rejected_count = excluded.rejected_count
                """,
                (log_id, clinic_id, log_date.isoformat(), now, total_rows, len(visits), rejected_count),
            )

            for v in visits:
                cur = self.db.conn.execute(
                    """
                    INSERT INTO visits
                        (log_id, visit_id, timestamp, doctor_id, payment_mode,
                         amount_paid_paise, discount_paise, is_refund)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        log_id, v.visit_id, v.timestamp.isoformat(), v.doctor_id,
                        v.payment_mode.value, v.amount_paid_paise, v.discount_paise,
                        int(v.is_refund),
                    ),
                )
                visit_row_id = cur.lastrowid
                for li in v.line_items:
                    self.db.conn.execute(
                        "INSERT INTO line_items (visit_row_id, drug_name, qty, unit_price_paise) "
                        "VALUES (?, ?, ?, ?)",
                        (visit_row_id, li.drug_name, li.qty, li.unit_price_paise),
                    )

        return log_id, clinic_id, log_date.isoformat()

    def save_reports_cache(
        self, log_id: str, reconciliation: ReconciliationReport, analytics: AnalyticsReport
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.conn:
            self.db.conn.execute(
                """
                INSERT INTO reports_cache (log_id, reconciliation_json, analytics_json, computed_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(log_id) DO UPDATE SET
                    reconciliation_json = excluded.reconciliation_json,
                    analytics_json = excluded.analytics_json,
                    computed_at = excluded.computed_at
                """,
                (log_id, reconciliation.model_dump_json(), analytics.model_dump_json(), now),
            )

    # ---------- reads ----------

    def list_logs(self) -> list[dict]:
        rows = self.db.conn.execute(
            "SELECT log_id, clinic_id, log_date, valid_count, rejected_count, uploaded_at "
            "FROM billing_logs ORDER BY log_date DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def log_exists(self, log_id: str) -> bool:
        row = self.db.conn.execute(
            "SELECT 1 FROM billing_logs WHERE log_id = ?", (log_id,)
        ).fetchone()
        return row is not None

    def get_visits(self, log_id: str) -> list[Visit]:
        """Raises HTTPException(404) if the log doesn't exist — reads are
        the one place we let this repository speak HTTP, since every
        route needs this exact 404 behavior and repeating it in every
        endpoint would be duplication."""
        log_row = self.db.conn.execute(
            "SELECT clinic_id FROM billing_logs WHERE log_id = ?", (log_id,)
        ).fetchone()
        if log_row is None:
            raise HTTPException(status_code=404, detail=f"No log found with log_id '{log_id}'")

        clinic_id = log_row["clinic_id"]
        visit_rows = self.db.conn.execute(
            "SELECT * FROM visits WHERE log_id = ? ORDER BY id", (log_id,)
        ).fetchall()

        visits: list[Visit] = []
        for row in visit_rows:
            li_rows = self.db.conn.execute(
                "SELECT drug_name, qty, unit_price_paise FROM line_items WHERE visit_row_id = ?",
                (row["id"],),
            ).fetchall()
            line_items = [
                LineItem(drug_name=r["drug_name"], qty=r["qty"], unit_price_paise=r["unit_price_paise"])
                for r in li_rows
            ]
            visits.append(
                Visit(
                    clinic_id=clinic_id,
                    visit_id=row["visit_id"],
                    timestamp=row["timestamp"],
                    doctor_id=row["doctor_id"],
                    line_items=line_items,
                    payment_mode=PaymentMode(row["payment_mode"]),
                    is_refund=bool(row["is_refund"]),
                    amount_paid_paise=row["amount_paid_paise"],
                    discount_paise=row["discount_paise"],
                )
            )
        return visits

    def get_cached_reconciliation(self, log_id: str) -> ReconciliationReport:
        row = self.db.conn.execute(
            "SELECT reconciliation_json FROM reports_cache WHERE log_id = ?", (log_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"No reconciliation report cached for log_id '{log_id}'",
            )
        return ReconciliationReport(**json.loads(row["reconciliation_json"]))

    def get_cached_analytics(self, log_id: str) -> AnalyticsReport:
        row = self.db.conn.execute(
            "SELECT analytics_json FROM reports_cache WHERE log_id = ?", (log_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"No analytics report cached for log_id '{log_id}'",
            )
        return AnalyticsReport(**json.loads(row["analytics_json"]))

    def get_log_meta(self, log_id: str) -> dict:
        row = self.db.conn.execute(
            "SELECT clinic_id, log_date FROM billing_logs WHERE log_id = ?", (log_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"No log found with log_id '{log_id}'")
        return dict(row)

    # ---------- narrative ----------

    def save_narrative(self, log_id: str, content: NarrativeContent, grounding_status: str) -> str:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.conn:
            self.db.conn.execute(
                """
                INSERT INTO narratives (log_id, narrative_json, grounding_status, generated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(log_id) DO UPDATE SET
                    narrative_json = excluded.narrative_json,
                    grounding_status = excluded.grounding_status,
                    generated_at = excluded.generated_at
                """,
                (log_id, content.model_dump_json(), grounding_status, now),
            )
        return now

    def get_narrative(self, log_id: str) -> tuple[NarrativeContent, str, str] | None:
        """Returns None if no narrative has been generated yet for this
        log — distinct from log_id not existing at all, which callers
        should check separately via log_exists()."""
        row = self.db.conn.execute(
            "SELECT narrative_json, grounding_status, generated_at FROM narratives WHERE log_id = ?",
            (log_id,),
        ).fetchone()
        if row is None:
            return None
        content = NarrativeContent(**json.loads(row["narrative_json"]))
        return content, row["grounding_status"], row["generated_at"]