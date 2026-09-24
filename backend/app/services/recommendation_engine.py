"""
Recommendation engine — converts raw analytics into actionable advice.
Generates recommendations per page: feedback, trends, alerts, predictions.
"""

from app.db.database import get_connection


def _rec(priority: str, category: str, message: str, action: str) -> dict:
    return {
        "priority": priority,       # high | medium | low
        "category": category,        # product | symptom | trend | alert | prediction
        "message": message,
        "action": action,
    }


def recommendations_for_overview() -> list[dict]:
    """Top-line recommendations shown on Overview page."""
    recs = []
    with get_connection() as conn:
        with conn.cursor() as cur:

            # Highest complaint volume product
            cur.execute("""
                SELECT COALESCE(p.name, 'Unclassified') AS product,
                       COUNT(*) AS complaints,
                       COUNT(*) FILTER (WHERE ci.severity = 'High') AS high_sev
                FROM complaints c
                LEFT JOIN products p ON p.id = c.product_id
                LEFT JOIN complaint_insights ci ON ci.complaint_id = c.id
                GROUP BY p.name
                ORDER BY complaints DESC
                LIMIT 1
            """)
            row = cur.fetchone()
            if row and row["complaints"] > 0:
                recs.append(_rec(
                    "high", "product",
                    f"{row['product']} has the highest complaint volume ({row['complaints']} records, {row['high_sev']} high-severity).",
                    f"Inspect {row['product']} recent production batches and quality logs."
                ))

            # Top symptom trending
            cur.execute("""
                SELECT symptom AS label, COUNT(*) AS count
                FROM complaint_insights ci
                CROSS JOIN LATERAL regexp_split_to_table(ci.symptoms, '\\s*,\\s*') AS symptom
                WHERE ci.symptoms IS NOT NULL AND trim(symptom) <> ''
                GROUP BY symptom
                ORDER BY count DESC
                LIMIT 1
            """)
            row = cur.fetchone()
            if row:
                recs.append(_rec(
                    "medium", "symptom",
                    f"'{row['label']}' is the most reported symptom ({row['count']} records).",
                    "Prioritize root-cause analysis on this symptom cluster."
                ))

            # Overall high severity count
            cur.execute("""
                SELECT COUNT(*) AS c FROM complaint_insights WHERE severity = 'High'
            """)
            high = cur.fetchone()["c"]
            if high > 0:
                recs.append(_rec(
                    "high" if high > 20 else "medium", "alert",
                    f"{high} high-severity complaints require attention.",
                    "Schedule a QA review meeting to triage these cases."
                ))

    return recs[:4]


def recommendations_for_analysis() -> list[dict]:
    """Recommendations for Analysis page — root cause focused."""
    recs = []
    with get_connection() as conn:
        with conn.cursor() as cur:

            # Top predicted cause
            cur.execute("""
                SELECT predicted_cause AS cause, ROUND(AVG(probability),1) AS prob,
                       COUNT(*) AS n
                FROM predictions
                GROUP BY predicted_cause
                ORDER BY prob DESC NULLS LAST
                LIMIT 3
            """)
            for row in cur.fetchall():
                prob = float(row["prob"] or 0)
                priority = "high" if prob >= 60 else "medium"
                recs.append(_rec(
                    priority, "prediction",
                    f"'{row['cause']}' predicted with {prob}% confidence across {row['n']} records.",
                    f"Investigate {row['cause']} — verify with engineering team."
                ))

            # Dominant category
            cur.execute("""
                SELECT COALESCE(category, 'Uncategorized') AS cat, COUNT(*) AS n
                FROM complaint_insights
                GROUP BY category
                ORDER BY n DESC
                LIMIT 1
            """)
            row = cur.fetchone()
            if row:
                recs.append(_rec(
                    "medium", "symptom",
                    f"'{row['cat']}' is the dominant failure category ({row['n']} records).",
                    f"Focus quality initiatives on {row['cat'].lower()} subsystem."
                ))

    return recs[:4]


def recommendations_for_alerts() -> list[dict]:
    """Recommendations for Alerts page — what to do about warnings."""
    recs = []
    with get_connection() as conn:
        with conn.cursor() as cur:

            # Device with most alerts
            cur.execute("""
                SELECT COALESCE(p.name, 'Unknown') AS product, COUNT(*) AS n
                FROM alerts a
                LEFT JOIN products p ON p.id = a.product_id
                WHERE a.resolved = FALSE AND a.product_id IS NOT NULL
                GROUP BY p.name
                ORDER BY n DESC
                LIMIT 1
            """)
            row = cur.fetchone()
            if row:
                recs.append(_rec(
                    "high", "alert",
                    f"{row['product']} triggered {row['n']} active alerts.",
                    f"Assign an owner for {row['product']} investigation this week."
                ))

            # Systemic patterns
            cur.execute("""
                SELECT COUNT(*) AS n FROM alerts
                WHERE resolved = FALSE AND type LIKE 'pattern%'
            """)
            n = cur.fetchone()["n"]
            if n > 0:
                recs.append(_rec(
                    "medium", "alert",
                    f"{n} systemic patterns detected across multiple products.",
                    "Review cross-product quality — potential shared component."
                ))

            # Safety alerts
            cur.execute("""
                SELECT COUNT(*) AS n FROM alerts
                WHERE resolved = FALSE AND type = 'safety_symptom'
            """)
            n = cur.fetchone()["n"]
            if n > 0:
                recs.append(_rec(
                    "high", "alert",
                    f"{n} safety-related alerts (smell/smoke/sparks) active.",
                    "Escalate to compliance and safety team immediately."
                ))

    return recs[:4]


def recommendations_for_trends() -> list[dict]:
    """Recommendations for Trends page — strategic view."""
    recs = []
    with get_connection() as conn:
        with conn.cursor() as cur:

            # This week vs last week
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE created_at >= DATE_TRUNC('week', CURRENT_DATE)) AS tw,
                    COUNT(*) FILTER (
                        WHERE created_at >= DATE_TRUNC('week', CURRENT_DATE) - INTERVAL '1 week'
                          AND created_at < DATE_TRUNC('week', CURRENT_DATE)
                    ) AS lw
                FROM complaints
            """)
            row = cur.fetchone()
            tw, lw = row["tw"] or 0, row["lw"] or 0
            if lw > 0:
                change = ((tw - lw) / lw) * 100
                if change > 10:
                    recs.append(_rec(
                        "high", "trend",
                        f"Feedback volume increased {change:.0f}% this week vs last week.",
                        "Add temporary QA capacity to handle the surge."
                    ))
                elif change < -10:
                    recs.append(_rec(
                        "low", "trend",
                        f"Feedback volume decreased {abs(change):.0f}% this week.",
                        "Positive trend — investigate what changed and reinforce it."
                    ))
                else:
                    recs.append(_rec(
                        "medium", "trend",
                        f"Feedback volume stable (change: {change:+.0f}%).",
                        "Maintain current quality processes."
                    ))

            # Peak month
            cur.execute("""
                SELECT DATE_TRUNC('month', created_at)::date AS m, COUNT(*) AS n
                FROM complaints
                GROUP BY m ORDER BY n DESC LIMIT 1
            """)
            row = cur.fetchone()
            if row:
                recs.append(_rec(
                    "medium", "trend",
                    f"Highest monthly volume in {row['m'].strftime('%B %Y')} ({row['n']} records).",
                    "Correlate with seasonal/product events from that period."
                ))

    return recs[:4]


def recommendations_for_all() -> dict:
    """Single call returning all recommendation groups."""
    return {
        "overview": recommendations_for_overview(),
        "analysis": recommendations_for_analysis(),
        "alerts": recommendations_for_alerts(),
        "trends": recommendations_for_trends(),
    }