from __future__ import annotations

import sqlite3


def main() -> None:
    conn = sqlite3.connect("swasthiq.db")
    cur = conn.cursor()
    print("swasthiq.db table counts:")
    for table in ["billing_logs", "visits", "line_items", "reports_cache", "narratives"]:
        count = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count}")
    conn.close()


if __name__ == "__main__":
    main()
