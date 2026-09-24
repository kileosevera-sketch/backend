"""
Check what's currently in the database. Read-only — safe to run anytime.
"""
from app.db.database import get_connection


TABLES = [
    "users", "customers", "products",
    "complaints", "complaint_insights",
    "warranty_claims", "service_records", "product_returns",
    "failures", "failure_causes", "predictions", "alerts", "sync_logs",
]


def main():
    print("\n" + "=" * 60)
    print("DATABASE INVENTORY")
    print("=" * 60)

    with get_connection() as conn:
        with conn.cursor() as cur:

            print("\n--- Row counts ---")
            for table in TABLES:
                cur.execute(f"SELECT COUNT(*) AS c FROM {table};")
                count = cur.fetchone()["c"]
                print(f"  {table:25s} {count:>6} rows")

            print("\n--- Complaints: source_record_id samples ---")
            cur.execute("""
                SELECT source_record_id, created_at
                FROM complaints
                ORDER BY id
                LIMIT 5;
            """)
            rows = cur.fetchall()
            if rows:
                for r in rows:
                    print(f"  {r['source_record_id']}  (created {r['created_at']})")
            else:
                print("  (no complaints in DB)")

            print("\n--- Recent sync_logs ---")
            cur.execute("""
                SELECT source_type, last_synced_at, records_processed, status
                FROM sync_logs
                ORDER BY last_synced_at DESC
                LIMIT 10;
            """)
            rows = cur.fetchall()
            if rows:
                for r in rows:
                    print(f"  {r['source_type']:18s} "
                          f"{r['last_synced_at']}  "
                          f"processed={r['records_processed']}  "
                          f"status={r['status']}")
            else:
                print("  (no sync logs)")

            print("\n--- Sample complaints ---")
            cur.execute("""
                SELECT id, source_record_id, description, created_at
                FROM complaints
                ORDER BY id
                LIMIT 3;
            """)
            rows = cur.fetchall()
            for r in rows:
                print(f"  #{r['id']}  {r['source_record_id']}")
                print(f"      {r['description'][:80]}")
                print(f"      created_at = {r['created_at']}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()