from fastapi import APIRouter, Depends
from app.services.recommendation_engine import recommendations_for_all
from app.core.deps import require_role
from app.db.database import get_connection
from app.schemas.dashboard import (
    CustomerServiceComplaints,
    EngineeringPredictions,
    ManagementSummary,
    ManagementTrend,
    QASummary,
)
from app.services.sync_service import run_sync

router = APIRouter(prefix="/dashboard", tags=["dashboards"])


@router.get("/overview")
def dashboard_overview():
    """
    Single overview endpoint for the unified dashboard.
    Returns: metrics, symptoms, products (real names), sentiment,
    severity, categories, trends, predictions, alerts (all types),
    pipeline runs.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:

            # ---------- Metrics ----------
            cur.execute("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE created_at >= DATE_TRUNC('week', CURRENT_DATE)) AS this_week,
                    COUNT(*) FILTER (
                        WHERE created_at >= DATE_TRUNC('week', CURRENT_DATE) - INTERVAL '1 week'
                          AND created_at < DATE_TRUNC('week', CURRENT_DATE)
                    ) AS last_week
                FROM complaints
            """)
            cc = cur.fetchone()

            cur.execute("""
                SELECT
                    COUNT(*) AS analyzed,
                    COUNT(*) FILTER (WHERE severity = 'High') AS high_severity,
                    COUNT(*) FILTER (WHERE sentiment = 'Negative') AS negative_sentiment
                FROM complaint_insights
            """)
            ic = cur.fetchone()

            cur.execute("""
                SELECT COUNT(*) AS c FROM alerts WHERE resolved = FALSE
            """)
            active_alerts = cur.fetchone()["c"]

            # ---------- Symptoms (with full labels) ----------
            cur.execute("""
                SELECT symptom AS label, COUNT(*) AS count
                FROM complaint_insights ci
                CROSS JOIN LATERAL regexp_split_to_table(ci.symptoms, '\\s*,\\s*') AS symptom
                WHERE ci.symptoms IS NOT NULL AND trim(symptom) <> ''
                GROUP BY symptom
                ORDER BY count DESC
                LIMIT 10
            """)
            symptoms = cur.fetchall()

            # ---------- Products with REAL names ----------
            cur.execute("""
                SELECT
                    COALESCE(p.name, 'Unclassified') AS product,
                    COUNT(*) AS complaints,
                    COUNT(*) FILTER (WHERE ci.severity = 'High') AS high_severity
                FROM complaints c
                LEFT JOIN products p ON p.id = c.product_id
                LEFT JOIN complaint_insights ci ON ci.complaint_id = c.id
                GROUP BY p.name
                ORDER BY complaints DESC
                LIMIT 8
            """)
            products = cur.fetchall()

            # ---------- Sentiment ----------
            cur.execute("""
                SELECT COALESCE(sentiment, 'Unclassified') AS label, COUNT(*) AS count
                FROM complaint_insights
                GROUP BY sentiment
                ORDER BY count DESC
            """)
            sentiment = cur.fetchall()

            # ---------- Severity ----------
            cur.execute("""
                SELECT COALESCE(severity, 'Unclassified') AS label, COUNT(*) AS count
                FROM complaint_insights
                GROUP BY severity
                ORDER BY count DESC
            """)
            severity = cur.fetchall()

            # ---------- Categories ----------
            cur.execute("""
                SELECT COALESCE(category, 'Uncategorized') AS label, COUNT(*) AS count
                FROM complaint_insights
                GROUP BY category
                ORDER BY count DESC
                LIMIT 8
            """)
            categories = cur.fetchall()

            # ---------- Symptom → Top Cause (for Analysis page) ----------
            cur.execute("""
                SELECT ci.symptoms AS symptom,
                       f.description AS cause,
                       COUNT(*) AS cases
                FROM failures f
                JOIN complaint_insights ci ON f.complaint_id = ci.complaint_id
                WHERE ci.symptoms IS NOT NULL
                GROUP BY ci.symptoms, f.description
                ORDER BY ci.symptoms, cases DESC
            """)
            rows = cur.fetchall()

            # Keep only top cause per symptom
            top_cause_map = {}
            for r in rows:
                s = r["symptom"]
                if s not in top_cause_map:
                    top_cause_map[s] = {"symptom": s, "cause": r["cause"], "cases": r["cases"]}
            symptom_top_cause = sorted(top_cause_map.values(), key=lambda x: x["cases"], reverse=True)[:10]

            # ---------- Symptom → Failure links (for chart) ----------
            cur.execute("""
                SELECT ci.symptoms AS symptom,
                       COALESCE(f.description, 'Failure not recorded') AS failure,
                       COUNT(*) AS links
                FROM complaint_insights ci
                JOIN failures f ON f.complaint_id = ci.complaint_id
                WHERE ci.symptoms IS NOT NULL
                GROUP BY ci.symptoms, f.description
                ORDER BY links DESC
                LIMIT 40
            """)
            symptom_failure_links = cur.fetchall()

            # ---------- Predictions (all) ----------
            cur.execute("""
                SELECT COALESCE(predicted_cause, 'Unspecified') AS cause,
                       ROUND(AVG(probability), 1) AS probability,
                       COUNT(*) AS predictions,
                       MAX(evidence_summary) AS evidence
                FROM predictions
                GROUP BY predicted_cause
                ORDER BY probability DESC NULLS LAST, predictions DESC
            """)
            predictions = cur.fetchall()

            # ---------- Alerts (all types) ----------
            cur.execute("""
                SELECT a.type, a.message, a.severity, a.created_at,
                       COALESCE(p.name, '') AS product
                FROM alerts a
                LEFT JOIN products p ON p.id = a.product_id
                WHERE a.resolved = FALSE
                ORDER BY a.created_at DESC
                LIMIT 30
            """)
            alerts = cur.fetchall()

            # ---------- Weekly trend (12 weeks) ----------
            cur.execute("""
                SELECT DATE_TRUNC('week', created_at)::date AS bucket,
                       COUNT(*) AS count
                FROM complaints
                WHERE created_at >= CURRENT_DATE - INTERVAL '12 weeks'
                GROUP BY bucket ORDER BY bucket
            """)
            weekly_trend = cur.fetchall()

            # ---------- Monthly trend (6 months) ----------
            cur.execute("""
                SELECT DATE_TRUNC('month', created_at)::date AS bucket,
                       COUNT(*) AS count
                FROM complaints
                WHERE created_at >= CURRENT_DATE - INTERVAL '6 months'
                GROUP BY bucket ORDER BY bucket
            """)
            monthly_trend = cur.fetchall()

            # ---------- Pipeline runs ----------
            cur.execute("""
                SELECT source_type, last_synced_at, records_processed, status
                FROM sync_logs
                WHERE status = 'success'
                ORDER BY last_synced_at DESC
                LIMIT 10
            """)
            pipeline_runs = cur.fetchall()

            # ---------- Channels ----------
            cur.execute("""
                SELECT COALESCE(channel, 'Unknown') AS channel,
                       COUNT(*) AS complaints,
                       COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE - INTERVAL '7 days') AS last_7_days
                FROM complaints
                GROUP BY channel
                ORDER BY complaints DESC
            """)
            channels = cur.fetchall()

    total = cc["total"] or 0
    analyzed = ic["analyzed"] or 0

    def ser(row):
        return dict(row)

    # Serialize dates
    for row in alerts:
        row["created_at"] = row["created_at"].isoformat()
    for row in pipeline_runs:
        row["last_synced_at"] = row["last_synced_at"].isoformat()
    for row in weekly_trend:
        row["bucket"] = row["bucket"].isoformat()
    for row in monthly_trend:
        row["bucket"] = row["bucket"].isoformat()
    for row in predictions:
        if row["probability"] is not None:
            row["probability"] = float(row["probability"])

    return {
        "metrics": {
            "total_complaints": total,
            "this_week_complaints": cc["this_week"] or 0,
            "last_week_complaints": cc["last_week"] or 0,
            "analyzed_complaints": analyzed,
            "high_severity": ic["high_severity"] or 0,
            "negative_sentiment": ic["negative_sentiment"] or 0,
            "active_alerts": active_alerts,
        },
        "symptoms": [ser(r) for r in symptoms],
        "products": [ser(r) for r in products],
        "sentiment": [ser(r) for r in sentiment],
        "severity": [ser(r) for r in severity],
        "categories": [ser(r) for r in categories],
        "symptom_top_cause": symptom_top_cause,
        "symptom_failure_links": [ser(r) for r in symptom_failure_links],
        "predictions": [ser(r) for r in predictions],
        "alerts": [ser(r) for r in alerts],
        "weekly_trend": [ser(r) for r in weekly_trend],
        "monthly_trend": [ser(r) for r in monthly_trend],
        "pipeline_runs": [ser(r) for r in pipeline_runs],
        "channels": [ser(r) for r in channels],
    }


@router.get("/management/summary", response_model=ManagementSummary)
def management_summary(_user=Depends(require_role("admin", "management"))):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM complaints")
            total_complaints = cur.fetchone()["count"]
            cur.execute("SELECT COUNT(*) AS count FROM failures")
            total_failures = cur.fetchone()["count"]
            cur.execute("SELECT COALESCE(SUM(cost), 0) AS total FROM warranty_claims")
            total_warranty_cost = cur.fetchone()["total"]
            cur.execute("SELECT COUNT(*) AS count FROM alerts WHERE resolved = FALSE")
            active_alerts = cur.fetchone()["count"]
            cur.execute("""
                SELECT cause_name AS cause, COUNT(*) AS occurrences
                FROM failure_causes
                WHERE cause_name IS NOT NULL
                GROUP BY cause_name
                ORDER BY occurrences DESC
                LIMIT 5
            """)
            top_failure_causes = cur.fetchall()

    return {
        "total_complaints": total_complaints,
        "total_failures": total_failures,
        "total_warranty_cost": float(total_warranty_cost),
        "active_alerts": active_alerts,
        "top_failure_causes": top_failure_causes,
    }


@router.get("/management/trend", response_model=ManagementTrend)
def management_trend(_user=Depends(require_role("admin", "management"))):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT created_at::date AS date, COUNT(*) AS count
                FROM complaints
                WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY created_at::date
                ORDER BY date
            """)
            trend = cur.fetchall()
    return {"trend": [{"date": r["date"].isoformat(), "count": r["count"]} for r in trend]}


@router.get("/engineering/predictions", response_model=EngineeringPredictions)
def engineering_predictions(_user=Depends(require_role("admin", "engineering"))):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT symptom, predicted_cause, probability, evidence_summary
                FROM predictions
                ORDER BY probability DESC, created_at DESC
            """)
            predictions = cur.fetchall()
    return {"predictions": [{**p, "probability": float(p["probability"])} for p in predictions]}


@router.get("/qa/summary", response_model=QASummary)
def qa_summary(_user=Depends(require_role("admin", "qa"))):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(ci.severity, 'Unknown') AS severity, COUNT(*) AS count
                FROM complaint_insights ci GROUP BY ci.severity ORDER BY count DESC
            """)
            by_sev = cur.fetchall()
            cur.execute("""
                SELECT COALESCE(ci.sentiment, 'Unknown') AS sentiment, COUNT(*) AS count
                FROM complaint_insights ci GROUP BY ci.sentiment ORDER BY count DESC
            """)
            by_sent = cur.fetchall()
            cur.execute("""
                SELECT type, product_id, message, severity
                FROM alerts WHERE resolved = FALSE ORDER BY created_at DESC
            """)
            active_alerts = cur.fetchall()
    return {
        "complaints_by_severity": by_sev,
        "complaints_by_sentiment": by_sent,
        "active_alerts": active_alerts,
    }


@router.get("/customer-service/complaints", response_model=CustomerServiceComplaints)
def customer_service_complaints(_user=Depends(require_role("admin", "customer_service"))):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.id, c.description, c.status, c.channel, c.created_at,
                       ci.sentiment, ci.severity, ci.category, ci.symptoms
                FROM complaints c
                LEFT JOIN complaint_insights ci ON ci.complaint_id = c.id
                ORDER BY
                    CASE ci.severity
                        WHEN 'High' THEN 1 WHEN 'Medium' THEN 2
                        WHEN 'Low' THEN 3 ELSE 4 END,
                    c.created_at DESC
            """)
            complaints = cur.fetchall()
    return {"complaints": complaints}


@router.post("/sync")
def sync_new_feedback(records_per_source: int = 350):
    """Weekly sync — fetches the last week's feedback."""
    return run_sync(advance_mock_week=True, records_per_source=records_per_source)


@router.get("/trends/weekly")
def trends_weekly(weeks: int = 12):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DATE_TRUNC('week', created_at)::date AS bucket,
                       COUNT(*) AS count
                FROM complaints
                WHERE created_at >= CURRENT_DATE - make_interval(weeks => %s)
                GROUP BY bucket ORDER BY bucket
            """, (weeks,))
            rows = cur.fetchall()
    return {
        "period": "weekly",
        "buckets": [{"label": r["bucket"].strftime("%d %b"), "count": r["count"]} for r in rows],
    }


@router.get("/trends/monthly")
def trends_monthly(months: int = 6):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DATE_TRUNC('month', created_at)::date AS bucket,
                       COUNT(*) AS count
                FROM complaints
                WHERE created_at >= CURRENT_DATE - make_interval(months => %s)
                GROUP BY bucket ORDER BY bucket
            """, (months,))
            rows = cur.fetchall()
    return {
        "period": "monthly",
        "buckets": [{"label": r["bucket"].strftime("%b %Y"), "count": r["count"]} for r in rows],
    }

@router.get("/recommendations")
def dashboard_recommendations():
    """Recommendation engine output for all pages."""
    return recommendations_for_all()

@router.get("/weekly-comparison")
def weekly_comparison():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE created_at >= DATE_TRUNC('week', CURRENT_DATE)) AS this_week,
                    COUNT(*) FILTER (
                        WHERE created_at >= DATE_TRUNC('week', CURRENT_DATE) - INTERVAL '1 week'
                          AND created_at < DATE_TRUNC('week', CURRENT_DATE)
                    ) AS last_week
                FROM complaints
            """)
            row = cur.fetchone()
    tw = row["this_week"] or 0
    lw = row["last_week"] or 0
    return {
        "this_week": tw,
        "last_week": lw,
        "change": tw - lw,
        "change_pct": round(((tw - lw) / lw) * 100, 1) if lw else 0,
    }