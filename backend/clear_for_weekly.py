from app.db.database import get_connection

with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            TRUNCATE complaints, complaint_insights, warranty_claims,
                     service_records, product_returns, failures,
                     failure_causes, predictions, alerts, sync_logs
            RESTART IDENTITY CASCADE;
        """)
    conn.commit()
    print("Cleared. Ready for weekly seed.")