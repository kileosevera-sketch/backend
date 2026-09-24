from app.services.pattern_detector import detect_patterns
import os
from datetime import datetime

import httpx

from app.db.database import get_connection
from app.ai.complaint_analyzer import analyze_complaint


SOURCE_BASE_URL = os.getenv("SOURCE_BASE_URL", "http://localhost:8001/org")
SOURCE_TIMEOUT = 30


# ---------------------------------------------------------------------
# Checkpoint helpers — track last_synced_at per source
# ---------------------------------------------------------------------
def _get_last_sync(cur, source_type: str) -> datetime:
    cur.execute(
        "SELECT last_synced_at FROM sync_logs "
        "WHERE source_type = %s AND status = 'success' "
        "ORDER BY last_synced_at DESC LIMIT 1;",
        (source_type,),
    )
    row = cur.fetchone()
    if row and row["last_synced_at"]:
        return row["last_synced_at"]
    return datetime(1970, 1, 1)


def _record_sync(cur, source_type: str, processed: int, status: str):
    cur.execute(
        """
        INSERT INTO sync_logs (source_type, last_synced_at, records_processed, status)
        VALUES (%s, %s, %s, %s);
        """,
        (source_type, datetime.utcnow(), processed, status),
    )


# ---------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------
def _fetch_new(endpoint: str, since: datetime) -> list[dict]:
    url = f"{SOURCE_BASE_URL}/{endpoint}/new"
    params = {"since": since.isoformat()}
    with httpx.Client(timeout=SOURCE_TIMEOUT) as client:
        r = client.get(url, params=params)
        r.raise_for_status()
        return r.json()


def _load_complaints(cur, records: list[dict]) -> int:
    inserted = 0
    for r in records:
        product_id = r.get("product_id")
        if not product_id and r.get("product_name"):
            cur.execute("SELECT id FROM products WHERE name = %s LIMIT 1;", (r["product_name"],))
            prow = cur.fetchone()
            if prow:
                product_id = prow["id"]

        cur.execute(
            """
            INSERT INTO complaints
                (description, channel, status, source_record_id, created_at, product_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_record_id) DO NOTHING
            RETURNING id;
            """,
            (
                r.get("description", ""),
                r.get("channel"),
                r.get("status", "open"),
                r.get("source_record_id"),
                r.get("created_at"),
                product_id,
            ),
        )
        if cur.fetchone():
            inserted += 1
    return inserted


def _load_warranty_claims(cur, records: list[dict]) -> int:
    inserted = 0
    for r in records:
        cur.execute(
            """
            INSERT INTO warranty_claims
                (claim_date, status, cost, source_record_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (source_record_id) DO NOTHING
            RETURNING id;
            """,
            (
                r.get("claim_date"),
                r.get("status"),
                r.get("cost"),
                r.get("source_record_id"),
            ),
        )
        if cur.fetchone():
            inserted += 1
    return inserted


def _load_service_records(cur, records: list[dict]) -> int:
    inserted = 0
    for r in records:
        cur.execute(
            """
            INSERT INTO service_records
                (service_date, description, technician_notes, source_record_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (source_record_id) DO NOTHING
            RETURNING id;
            """,
            (
                r.get("service_date"),
                r.get("description"),
                r.get("technician_notes"),
                r.get("source_record_id"),
            ),
        )
        if cur.fetchone():
            inserted += 1
    return inserted


def _load_product_returns(cur, records: list[dict]) -> int:
    inserted = 0
    for r in records:
        cur.execute(
            """
            INSERT INTO product_returns
                (return_date, reason, source_record_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (source_record_id) DO NOTHING
            RETURNING id;
            """,
            (
                r.get("return_date"),
                r.get("reason"),
                r.get("source_record_id"),
            ),
        )
        if cur.fetchone():
            inserted += 1
    return inserted


def _load_failures(cur, records: list[dict]) -> int:
    inserted = 0
    for r in records:
        complaint_id = None
        linked_sid = r.get("complaint_source_record_id")
        if linked_sid:
            cur.execute(
                "SELECT id FROM complaints WHERE source_record_id = %s;",
                (linked_sid,),
            )
            crow = cur.fetchone()
            if crow:
                complaint_id = crow["id"]

        cur.execute(
            """
            INSERT INTO failures
                (complaint_id, failure_date, description, source_record_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (source_record_id) DO NOTHING
            RETURNING id;
            """,
            (
                complaint_id,
                r.get("failure_date"),
                r.get("description"),
                r.get("source_record_id"),
            ),
        )
        if cur.fetchone():
            inserted += 1
    return inserted


# ---------------------------------------------------------------------
# NLP analysis
# ---------------------------------------------------------------------
def _analyze_new_complaints(cur) -> int:
    cur.execute(
        """
        SELECT c.id, c.description
        FROM complaints c
        LEFT JOIN complaint_insights ci ON ci.complaint_id = c.id
        WHERE ci.id IS NULL
        ORDER BY c.id;
        """
    )
    pending = cur.fetchall()
    analyzed = 0
    for row in pending:
        result = analyze_complaint(row["description"])
        cur.execute(
            """
            INSERT INTO complaint_insights
                (complaint_id, sentiment, severity, symptoms, category,
                 processed_text, model_version, confidence)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (
                row["id"],
                result["sentiment"],
                result["severity"],
                result["symptoms"],
                result["category"],
                result["processed_text"],
                result["model_version"],
                None,
            ),
        )
        analyzed += 1
    return analyzed


# ---------------------------------------------------------------------
# Failure cause ranking
# ---------------------------------------------------------------------
def _rank_failure_causes(cur) -> int:
    cur.execute(
        """
        SELECT ci.symptoms, f.description AS cause, COUNT(*) AS occurrences
        FROM failures f
        JOIN complaint_insights ci ON f.complaint_id = ci.complaint_id
        WHERE f.complaint_id IS NOT NULL AND ci.symptoms IS NOT NULL
        GROUP BY ci.symptoms, f.description
        ORDER BY ci.symptoms, occurrences DESC;
        """
    )
    rows = cur.fetchall()
    if not rows:
        return 0

    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row["symptoms"], []).append(row)

    cur.execute("DELETE FROM predictions;")

    total = 0
    for symptom, causes in groups.items():
        total_occ = sum(c["occurrences"] for c in causes)
        for c in causes:
            prob = round((c["occurrences"] / total_occ) * 100, 2)
            evidence = (
                f"{c['occurrences']} out of {total_occ} historical cases "
                f"with this symptom resulted in this cause."
            )
            cur.execute(
                """
                INSERT INTO predictions (symptom, predicted_cause, probability, evidence_summary)
                VALUES (%s, %s, %s, %s);
                """,
                (symptom, c["cause"], prob, evidence),
            )
            total += 1
    return total


# ---------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------
def _detect_anomalies(cur) -> int:
    cur.execute("DELETE FROM alerts WHERE resolved = FALSE;")
    alerts_created = 0

    cur.execute(
        """
        SELECT p.id, p.name, COUNT(*) AS high_count
        FROM complaints c
        JOIN products p ON p.id = c.product_id
        JOIN complaint_insights ci ON ci.complaint_id = c.id
        WHERE ci.severity = 'High'
        GROUP BY p.id, p.name
        HAVING COUNT(*) >= 3
        ORDER BY high_count DESC;
        """
    )
    for row in cur.fetchall():
        msg = (
            f"{row['high_count']} high-severity complaints recorded for "
            f"{row['name']}. Review urgently."
        )
        cur.execute(
            "INSERT INTO alerts (type, product_id, message, severity, resolved) "
            "VALUES ('high_severity_cluster', %s, %s, 'high', FALSE);",
            (row["id"], msg),
        )
        alerts_created += 1

    cur.execute(
        """
        SELECT COUNT(*) AS c FROM complaint_insights
        WHERE symptoms ILIKE '%smell%' OR symptoms ILIKE '%smoke%' OR symptoms ILIKE '%spark%';
        """
    )
    danger = cur.fetchone()["c"]
    if danger >= 2:
        msg = (
            f"{danger} complaints report dangerous symptoms "
            f"(smell / smoke / sparks). Safety review recommended."
        )
        cur.execute(
            "INSERT INTO alerts (type, product_id, message, severity, resolved) "
            "VALUES ('safety_symptom', NULL, %s, 'high', FALSE);",
            (msg,),
        )
        alerts_created += 1

    return alerts_created


# ---------------------------------------------------------------------
# PUBLIC ENTRY POINT
# ---------------------------------------------------------------------
def run_sync(advance_mock_week: bool = True, records_per_source: int = 350) -> dict:
    summary = {
        "started_at": datetime.utcnow().isoformat(),
        "advanced_mock": False,
        "advanced_count": records_per_source,
        "sources": {},
        "analyzed": 0,
        "predictions_refreshed": 0,
        "alerts_created": 0,
        "patterns_detected": 0,
        "stages": [],
        "total_inserted": 0,
    }

    if advance_mock_week:
        try:
            with httpx.Client(timeout=120) as client:
                r = client.post(
                    f"{SOURCE_BASE_URL}/advance-week",
                    params={"records_per_source": records_per_source},
                )
                if r.status_code == 200:
                    resp = r.json()
                    summary["advanced_mock"] = True
                    summary["mock_mode"] = resp.get("mode", "advanced")
                    summary["stages"].append({
                        "name": f"Mock {resp.get('mode', 'advanced')}",
                        "detail": f"{records_per_source} records per source",
                        "status": "done",
                    })
        except Exception as e:
            summary["stages"].append({
                "name": "Mock advance",
                "detail": str(e),
                "status": "failed",
            })

    with get_connection() as conn:
        with conn.cursor() as cur:
            sources = [
                ("complaints", "complaints", _load_complaints),
                ("warranty_claims", "warranty-claims", _load_warranty_claims),
                ("service_records", "service-records", _load_service_records),
                ("product_returns", "product-returns", _load_product_returns),
                ("failures", "failures", _load_failures),
            ]

            for label, endpoint, loader in sources:
                since = _get_last_sync(cur, label)
                try:
                    records = _fetch_new(endpoint, since)
                    inserted = loader(cur, records)
                    _record_sync(cur, label, inserted, "success")
                    summary["sources"][label] = {
                        "fetched": len(records),
                        "inserted": inserted,
                    }
                    summary["total_inserted"] += inserted
                except Exception as e:
                    _record_sync(cur, label, 0, "failed")
                    summary["sources"][label] = {
                        "fetched": 0,
                        "inserted": 0,
                        "error": str(e),
                    }

            summary["analyzed"] = _analyze_new_complaints(cur)
            summary["predictions_refreshed"] = _rank_failure_causes(cur)
            summary["alerts_created"] = _detect_anomalies(cur)
            summary["patterns_detected"] = detect_patterns(min_complaints=5, min_products=2)

            conn.commit()

    summary["finished_at"] = datetime.utcnow().isoformat()
    return summary
