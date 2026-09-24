"""
Generate meaningful alerts from existing data:
- High-severity clusters per product
- Symptoms with unusually high volume
- Products with recent complaint spikes
"""
from app.db.database import get_connection


def generate_alerts():
    with get_connection() as conn:
        with conn.cursor() as cur:

            # Clear existing unresolved alerts (fresh snapshot)
            cur.execute("DELETE FROM alerts WHERE resolved = FALSE;")

            alerts_created = 0

            # --- Alert 1: High-severity clusters per product ---
            cur.execute("""
                SELECT
                    p.id AS product_id,
                    p.name AS product_name,
                    COUNT(*) AS high_count
                FROM complaints c
                JOIN products p ON p.id = c.product_id
                JOIN complaint_insights ci ON ci.complaint_id = c.id
                WHERE ci.severity = 'High'
                GROUP BY p.id, p.name
                HAVING COUNT(*) >= 3
                ORDER BY high_count DESC;
            """)
            for row in cur.fetchall():
                msg = (
                    f"{row['high_count']} high-severity complaints recorded for "
                    f"{row['product_name']}. Review urgently."
                )
                cur.execute("""
                    INSERT INTO alerts (type, product_id, message, severity, resolved)
                    VALUES ('high_severity_cluster', %s, %s, 'high', FALSE);
                """, (row["product_id"], msg))
                alerts_created += 1

            # --- Alert 2: Dangerous symptoms (smoke, spark, etc.) ---
            cur.execute("""
                SELECT COUNT(*) AS c
                FROM complaint_insights
                WHERE symptoms ILIKE '%smell%'
                   OR symptoms ILIKE '%smoke%'
                   OR symptoms ILIKE '%spark%';
            """)
            dangerous_count = cur.fetchone()["c"]
            if dangerous_count >= 2:
                msg = (
                    f"{dangerous_count} complaints report dangerous symptoms "
                    f"(smell / smoke / sparks). Safety review recommended."
                )
                cur.execute("""
                    INSERT INTO alerts (type, product_id, message, severity, resolved)
                    VALUES ('safety_symptom', NULL, %s, 'high', FALSE);
                """, (msg,))
                alerts_created += 1

            # --- Alert 3: Top symptom volume ---
            cur.execute("""
                SELECT symptom, COUNT(*) AS count
                FROM complaint_insights ci
                CROSS JOIN LATERAL regexp_split_to_table(ci.symptoms, '\\s*,\\s*') AS symptom
                WHERE ci.symptoms IS NOT NULL AND trim(symptom) <> ''
                GROUP BY symptom
                ORDER BY count DESC
                LIMIT 1;
            """)
            row = cur.fetchone()
            if row and row["count"] >= 10:
                msg = (
                    f"'{row['symptom']}' is the most reported symptom "
                    f"({row['count']} complaints). Investigate root cause."
                )
                cur.execute("""
                    INSERT INTO alerts (type, product_id, message, severity, resolved)
                    VALUES ('symptom_volume', NULL, %s, 'medium', FALSE);
                """, (msg,))
                alerts_created += 1

            conn.commit()

            print(f"\nAlerts created: {alerts_created}")


if __name__ == "__main__":
    generate_alerts()