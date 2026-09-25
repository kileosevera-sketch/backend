"""Seed a small repeatable dataset for local dashboard testing."""
from datetime import date, timedelta

from app.db.database import get_connection


CUSTOMERS = [
    ("Amina Mwinyi", "amina@example.com", "+255700100001", "Dar es Salaam"),
    ("Brian Otieno", "brian@example.com", "+254700100002", "Nairobi"),
    ("Grace Njeri", "grace@example.com", "+254700100003", "Mombasa"),
    ("David Kimaro", "david@example.com", "+255700100004", "Arusha"),
]

PRODUCTS = [
    ("AeroCool X1", "Air Conditioner", "AC-X1", date(2024, 2, 15)),
    ("AeroCool X2", "Air Conditioner", "AC-X2", date(2024, 8, 20)),
    ("PureBreeze Mini", "Air Purifier", "AP-MINI", date(2025, 1, 10)),
]

COMPLAINTS = [
    ("demo-complaint-001", 0, 0, "Unit makes a loud rattling noise after ten minutes of use.", "Phone", "open", 2),
    ("demo-complaint-002", 1, 0, "Air conditioner is not cooling the room properly.", "Email", "investigating", 5),
    ("demo-complaint-003", 2, 1, "The display turns off and the unit restarts unexpectedly.", "Web", "open", 9),
    ("demo-complaint-004", 3, 2, "Air purifier has a strong smell and reduced airflow.", "Phone", "resolved", 14),
    ("demo-complaint-005", 0, 1, "Remote control does not respond consistently.", "Email", "open", 22),
    ("demo-complaint-006", 1, 0, "Water is leaking from the indoor unit.", "Web", "investigating", 35),
]

INSIGHTS = [
    ("Negative", "Medium", "rattling noise", "Mechanical", 0, 0.94),
    ("Negative", "High", "not cooling, weak airflow", "Cooling", 1, 0.97),
    ("Negative", "High", "display off, restart", "Electrical", 2, 0.91),
    ("Negative", "Medium", "strong smell, reduced airflow", "Filter", 3, 0.88),
    ("Neutral", "Low", "remote control, intermittent response", "Controls", 4, 0.86),
    ("Negative", "High", "water leak", "Installation", 5, 0.96),
]


def find_or_create(cur, table, lookup_column, lookup_value, insert_sql, insert_values):
    cur.execute(f"SELECT id FROM {table} WHERE {lookup_column} = %s", (lookup_value,))
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute(insert_sql, insert_values)
    return cur.fetchone()["id"]


def run():
    with get_connection() as conn:
        with conn.cursor() as cur:
            customer_ids = [
                find_or_create(
                    cur,
                    "customers",
                    "email",
                    email,
                    """INSERT INTO customers (full_name, email, phone, region)
                       VALUES (%s, %s, %s, %s) RETURNING id""",
                    customer,
                )
                for customer in CUSTOMERS
                for email in [customer[1]]
            ]
            product_ids = [
                find_or_create(
                    cur,
                    "products",
                    "model_number",
                    model_number,
                    """INSERT INTO products (name, category, model_number, release_date)
                       VALUES (%s, %s, %s, %s) RETURNING id""",
                    product,
                )
                for product in PRODUCTS
                for model_number in [product[2]]
            ]

            complaint_ids = []
            for source_id, customer_index, product_index, description, channel, status, days_ago in COMPLAINTS:
                cur.execute("SELECT id FROM complaints WHERE source_record_id = %s", (source_id,))
                row = cur.fetchone()
                if row:
                    complaint_ids.append(row["id"])
                    continue
                created_at = date.today() - timedelta(days=days_ago)
                cur.execute(
                    """INSERT INTO complaints
                       (customer_id, product_id, description, channel, status, source_record_id, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                    (customer_ids[customer_index], product_ids[product_index], description,
                     channel, status, source_id, created_at),
                )
                complaint_ids.append(cur.fetchone()["id"])

            for insight, complaint_id in zip(INSIGHTS, complaint_ids):
                sentiment, severity, symptoms, category, _, confidence = insight
                cur.execute("SELECT id FROM complaint_insights WHERE complaint_id = %s", (complaint_id,))
                if not cur.fetchone():
                    cur.execute(
                        """INSERT INTO complaint_insights
                           (complaint_id, sentiment, severity, symptoms, category, processed_text, model_version, confidence)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                        (complaint_id, sentiment, severity, symptoms, category,
                         "Demo analysis generated for local testing", "demo-v1", confidence),
                    )

            demo_failures = [
                (complaint_ids[1], product_ids[0], "Compressor performance degradation", 18),
                (complaint_ids[2], product_ids[1], "Power board overheating", 9),
                (complaint_ids[5], product_ids[0], "Blocked condensate drain", 3),
            ]
            for complaint_id, product_id, description, days_ago in demo_failures:
                cur.execute("SELECT id FROM failures WHERE complaint_id = %s", (complaint_id,))
                failure = cur.fetchone()
                if failure:
                    failure_id = failure["id"]
                else:
                    cur.execute(
                        """INSERT INTO failures
                           (product_id, complaint_id, failure_date, description, source_record_id)
                           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                        (product_id, complaint_id, date.today() - timedelta(days=days_ago),
                         description, f"demo-failure-{complaint_id}"),
                    )
                    failure_id = cur.fetchone()["id"]
                cur.execute("SELECT id FROM failure_causes WHERE failure_id = %s", (failure_id,))
                if not cur.fetchone():
                    cur.execute(
                        """INSERT INTO failure_causes (failure_id, cause_name, probability, confidence)
                           VALUES (%s, %s, %s, %s)""",
                        (failure_id, description, 72.0, 0.88),
                    )

            predictions = [
                (product_ids[0], "Compressor performance degradation", 78.5, "Repeated cooling complaints and service history"),
                (product_ids[1], "Power board overheating", 64.0, "Restart pattern and high-severity electrical symptom"),
                (product_ids[2], "Filter saturation", 56.5, "Reduced airflow and odor complaints"),
            ]
            for product_id, cause, probability, evidence in predictions:
                cur.execute(
                    """SELECT id FROM predictions WHERE product_id = %s AND predicted_cause = %s""",
                    (product_id, cause),
                )
                if not cur.fetchone():
                    cur.execute(
                        """INSERT INTO predictions (product_id, predicted_cause, probability, evidence_summary)
                           VALUES (%s, %s, %s, %s)""",
                        (product_id, cause, probability, evidence),
                    )

            alerts = [
                ("high_failure_rate", product_ids[0], "AeroCool X1 has repeated cooling-related complaints.", "high"),
                ("quality_signal", product_ids[1], "AeroCool X2 shows a rising electrical restart pattern.", "medium"),
            ]
            for alert_type, product_id, message, severity in alerts:
                cur.execute(
                    "SELECT id FROM alerts WHERE type = %s AND product_id = %s AND resolved = FALSE",
                    (alert_type, product_id),
                )
                if not cur.fetchone():
                    cur.execute(
                        """INSERT INTO alerts (type, product_id, message, severity, resolved)
                           VALUES (%s, %s, %s, %s, FALSE)""",
                        (alert_type, product_id, message, severity),
                    )

            cur.execute(
                """INSERT INTO sync_logs (source_type, last_synced_at, records_processed, status)
                   SELECT 'demo_seed', NOW(), %s, 'success'
                   WHERE NOT EXISTS (
                       SELECT 1 FROM sync_logs WHERE source_type = 'demo_seed'
                   )""",
                (len(COMPLAINTS),),
            )

    print(f"Demo data ready: {len(CUSTOMERS)} customers, {len(PRODUCTS)} products, {len(COMPLAINTS)} complaints.")


if __name__ == "__main__":
    run()
