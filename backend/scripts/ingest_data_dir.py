from __future__ import annotations

import json
from pathlib import Path

from app.engine.analytics import compute_analytics
from app.engine.reconciliation import compute_reconciliation
from app.ingestion.parser import parse_billing_log
from app.storage.db import Database
from app.storage.repository import LogRepository


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    data_dir = root / "backend" / "data"
    db_path = root / "swasthiq.db"

    db = Database(str(db_path))
    repo = LogRepository(db)

    try:
        for path in sorted(data_dir.glob("*.json")):
            rows = json.loads(path.read_text(encoding="utf-8"))
            parsed = parse_billing_log(rows)

            if parsed.valid_count == 0:
                print(
                    json.dumps(
                        {
                            "file": path.name,
                            "status": "rejected_all_rows",
                            "total_rows": parsed.total_rows,
                            "valid_count": parsed.valid_count,
                            "rejected_count": parsed.rejected_count,
                        }
                    )
                )
                continue

            reconciliation = compute_reconciliation(parsed.valid_visits)
            analytics = compute_analytics(parsed.valid_visits)

            log_id, clinic_id, log_date = repo.upsert_log(
                visits=parsed.valid_visits,
                total_rows=parsed.total_rows,
                rejected_count=parsed.rejected_count,
            )
            repo.save_reports_cache(log_id, reconciliation, analytics)

            print(
                json.dumps(
                    {
                        "file": path.name,
                        "status": "ingested",
                        "log_id": log_id,
                        "clinic_id": clinic_id,
                        "log_date": log_date,
                        "total_rows": parsed.total_rows,
                        "valid_count": parsed.valid_count,
                        "rejected_count": parsed.rejected_count,
                    }
                )
            )

        print("---billing_logs_in_db---")
        for row in repo.list_logs():
            print(json.dumps(row))
    finally:
        db.close()


if __name__ == "__main__":
    main()
