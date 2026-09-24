"""Sprint 2 — anomaly detection.

Compares each product's complaint volume in the recent window against
its own historical daily rate. If recent volume is unusually high
(above SPIKE_THRESHOLD times the expected baseline), creates an alert.


Usage:
    python detect_anomalies.py
"""
from app.db.database import get_connection

RECENT_WINDOW_DAYS = 7
SPIKE_THRESHOLD = 1.5  # recent volume must exceed 1.5x the expected baseline


def detect_anomalies():
    with get_connection() as conn:
        with conn.cursor() as cur:

            # Recent complaint counts per product
            cur.execute(
                """
                SELECT product_id, COUNT(*) AS recent_count
                FROM complaints
                WHERE created_at >= NOW() - make_interval(days => %s)
                GROUP BY product_id;
                """,
                (RECENT_WINDOW_DAYS,),
            )
            recent = {row["product_id"]: row["recent_count"] for row in cur.fetchall()}

            # Historical baseline: daily rate from older complaints
            cur.execute(
                """
                SELECT
                    product_id,
                    COUNT(*) AS historical_count,
                    GREATEST(
                        EXTRACT(EPOCH FROM (MAX(created_at) - MIN(created_at))) / 86400,
                        1
                    ) AS span_days
                FROM complaints
                WHERE created_at < NOW() - make_interval(days => %s)
                GROUP BY product_id;
                """,
                (RECENT_WINDOW_DAYS,),
            )
            baseline_rows = cur.fetchall()

            cur.execute("SELECT id, name FROM products;")
            product_names = {row["id"]: row["name"] for row in cur.fetchall()}

            print("\n==============================================")
            print("ANOMALY DETECTION")
            print("==============================================")

            alerts_created = 0

            for row in baseline_rows:
                product_id = row["product_id"]
                product_name = product_names.get(product_id, f"Product {product_id}")
                historical_count = row["historical_count"]
                span_days = float(row["span_days"])
                daily_rate = historical_count / span_days
                expected_recent = daily_rate * RECENT_WINDOW_DAYS
                actual_recent = recent.get(product_id, 0)

                print(f"\n{product_name}:")
                print(f"  Historical daily rate: {daily_rate:.2f} complaints/day")
                print(f"  Expected in last {RECENT_WINDOW_DAYS} days: {expected_recent:.1f}")
                print(f"  Actual in last {RECENT_WINDOW_DAYS} days: {actual_recent}")

                if expected_recent > 0 and actual_recent > expected_recent * SPIKE_THRESHOLD:
                    increase_pct = ((actual_recent - expected_recent) / expected_recent) * 100

                    # Don't create a duplicate alert if one is already active
                    cur.execute(
                        """
                        SELECT id FROM alerts
                        WHERE type = 'complaint_spike'
                          AND product_id = %s
                          AND resolved = FALSE;
                        """,
                        (product_id,),
                    )
                    if cur.fetchone():
                        print("  Already has an active alert — skipping duplicate.")
                        continue

                    message = (
                        f"Complaints for {product_name} increased {increase_pct:.0f}% "
                        f"above the historical baseline in the last "
                        f"{RECENT_WINDOW_DAYS} days ({actual_recent} actual vs "
                        f"{expected_recent:.1f} expected)."
                    )
                    print(f"  ANOMALY DETECTED: {message}")

                    cur.execute(
                        """
                        INSERT INTO alerts (type, product_id, message, severity, resolved)
                        VALUES (%s, %s, %s, %s, FALSE);
                        """,
                        ("complaint_spike", product_id, message, "high"),
                    )
                    alerts_created += 1
                else:
                    print("  Normal — no alert.")

            conn.commit()

            print("\n==============================================")
            print("ANOMALY DETECTION COMPLETED")
            print("==============================================")
            print(f"Alerts created: {alerts_created}")


if __name__ == "__main__":
    detect_anomalies()