"""
SQLite connection + schema management.

Design choice: plain sqlite3, not an ORM. The brief explicitly says
"we're evaluating pipeline and API design, not infra plumbing" — an ORM
(SQLAlchemy etc.) would add a translation layer between our Pydantic
models and the DB that we don't need for 4 small tables. Raw SQL here is
also easier to audit for the "data consistency" story in the README:
you can read exactly what happens to the database, statement by statement.

Schema:
  billing_logs   — one row per ingested clinic-day (the parent resource)
  visits         — one row per visit, FK to billing_logs
  line_items     — one row per line item, FK to visits
  reports_cache  — pre-computed reconciliation + analytics JSON, FK to billing_logs
                   (computed once at ingestion time, since the brief says the
                   deterministic layer "must never call an LLM" and should be
                   ground truth — caching it means GET requests are instant
                   and never risk recomputing differently)
"""

from __future__ import annotations

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS billing_logs (
    log_id          TEXT PRIMARY KEY,
    clinic_id       TEXT NOT NULL,
    log_date        TEXT NOT NULL,
    uploaded_at     TEXT NOT NULL,
    total_rows      INTEGER NOT NULL,
    valid_count     INTEGER NOT NULL,
    rejected_count  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS visits (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    log_id              TEXT NOT NULL REFERENCES billing_logs(log_id),
    visit_id            TEXT NOT NULL,
    timestamp           TEXT NOT NULL,
    doctor_id           TEXT NOT NULL,
    payment_mode        TEXT NOT NULL,
    amount_paid_paise   INTEGER NOT NULL,
    discount_paise      INTEGER NOT NULL,
    is_refund           INTEGER NOT NULL  -- 0 or 1
);
CREATE INDEX IF NOT EXISTS idx_visits_log_id ON visits(log_id);

CREATE TABLE IF NOT EXISTS line_items (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_row_id        INTEGER NOT NULL REFERENCES visits(id),
    drug_name           TEXT NOT NULL,
    qty                 INTEGER NOT NULL,
    unit_price_paise    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_line_items_visit_row_id ON line_items(visit_row_id);

CREATE TABLE IF NOT EXISTS reports_cache (
    log_id                  TEXT PRIMARY KEY REFERENCES billing_logs(log_id),
    reconciliation_json     TEXT NOT NULL,
    analytics_json          TEXT NOT NULL,
    computed_at             TEXT NOT NULL
);
"""


class Database:
    """
    Thin wrapper around a single sqlite3 connection.

    One Database instance = one connection, held open for the process
    lifetime (or test lifetime). check_same_thread=False because FastAPI
    can service requests on different threads; we accept this tradeoff
    for a single-clinic take-home scope rather than building a connection
    pool, which would be over-engineering here.
    """

    def __init__(self, db_path: str = "swasthiq.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()