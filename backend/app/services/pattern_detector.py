"""
Pattern detector — general insights, not just device-specific alerts.
Aggregates complaints into symptom clusters and component clusters,
flags patterns that appear across multiple products.
"""

from app.db.database import get_connection


# Symptom keywords — how to classify a complaint into a pattern group
SYMPTOM_PATTERNS = {
    "motor_related": ["noise", "vibration", "shakes", "stops"],
    "cooling_related": ["not cooling", "cooling", "cold", "freezing"],
    "heating_related": ["not heating", "heating", "temperature"],
    "electrical_related": ["spark", "smoke", "smell", "burning", "short circuit"],
    "leakage_related": ["leak", "leaking", "water"],
    "sensor_related": ["error code", "sensor", "display", "reset"],
    "software_related": ["software", "frozen", "unresponsive", "cycle"],
}

PATTERN_LABELS = {
    "motor_related": "Motor / moving parts",
    "cooling_related": "Cooling system",
    "heating_related": "Heating system",
    "electrical_related": "Electrical system",
    "leakage_related": "Leakage / sealing",
    "sensor_related": "Sensors & controls",
    "software_related": "Software / firmware",
}


def detect_patterns(min_complaints: int = 5, min_products: int = 2):
    """
    Detect general patterns:
      - Symptom clusters across multiple products
      - Component clusters from failures
    Creates alerts for patterns that exceed thresholds.
    """
    alerts_created = 0

    with get_connection() as conn:
        with conn.cursor() as cur:

            # 1. Symptom-cluster patterns across products
            cur.execute("""
                SELECT ci.symptoms, c.product_id, p.name AS product_name
                FROM complaint_insights ci
                JOIN complaints c ON c.id = ci.complaint_id
                LEFT JOIN products p ON p.id = c.product_id
                WHERE ci.symptoms IS NOT NULL AND trim(ci.symptoms) <> ''
            """)
            rows = cur.fetchall()

            cluster_hits = {k: {"count": 0, "products": set()} for k in SYMPTOM_PATTERNS}

            for row in rows:
                symptoms_lower = row["symptoms"].lower()
                product_name = row["product_name"] or "Unknown"
                for cluster, keywords in SYMPTOM_PATTERNS.items():
                    if any(kw in symptoms_lower for kw in keywords):
                        cluster_hits[cluster]["count"] += 1
                        cluster_hits[cluster]["products"].add(product_name)

            for cluster, data in cluster_hits.items():
                count = data["count"]
                products = data["products"]
                if count >= min_complaints and len(products) >= min_products:
                    label = PATTERN_LABELS.get(cluster, cluster)
                    product_list = ", ".join(sorted(products)[:3])
                    msg = (
                        f"Pattern detected: {label} issues appeared across "
                        f"{len(products)} products ({product_list}) — {count} complaints. "
                        f"Possible systemic quality issue."
                    )
                    # Avoid duplicates — only create if no active alert with same message
                    cur.execute(
                        "SELECT id FROM alerts WHERE message = %s AND resolved = FALSE;",
                        (msg,),
                    )
                    if not cur.fetchone():
                        cur.execute(
                            "INSERT INTO alerts (type, product_id, message, severity, resolved) "
                            "VALUES ('pattern_general', NULL, %s, 'high', FALSE);",
                            (msg,),
                        )
                        alerts_created += 1

            # 2. Component-cluster patterns from failures
            cur.execute("""
                SELECT f.description AS cause, COUNT(*) AS count
                FROM failures f
                WHERE f.description IS NOT NULL
                GROUP BY f.description
                ORDER BY count DESC
            """)
            causes = cur.fetchall()

            for row in causes:
                cause = row["cause"]
                count = row["count"]
                if count >= min_complaints:
                    msg = (
                        f"Component pattern: '{cause}' recorded {count} times in "
                        f"historical failures. Investigate supplier / batch quality."
                    )
                    cur.execute(
                        "SELECT id FROM alerts WHERE message = %s AND resolved = FALSE;",
                        (msg,),
                    )
                    if not cur.fetchone():
                        cur.execute(
                            "INSERT INTO alerts (type, product_id, message, severity, resolved) "
                            "VALUES ('pattern_component', NULL, %s, 'medium', FALSE);",
                            (msg,),
                        )
                        alerts_created += 1

            conn.commit()

    return alerts_created