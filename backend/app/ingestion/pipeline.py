"""Extract -> Validate -> Transform -> Load -> Log, for each data source
coming from the organization system (currently the mock API).
"""
from datetime import datetime, timezone

from app.db.database import get_connection
from app.ingestion.client import fetch


# ---------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------

def _get_or_create_product(cur, name: str) -> int:
    cur.execute("SELECT id FROM products WHERE name = %s", (name,))
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute(
        "INSERT INTO products (name, category) VALUES (%s, %s) RETURNING id",
        (name, "unspecified"),
    )
    return cur.fetchone()["id"]


def _get_or_create_customer(cur, name: str, email: str) -> int:
    cur.execute("SELECT id FROM customers WHERE email = %s", (email,))
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute(
        "INSERT INTO customers (full_name, email) VALUES (%s, %s) RETURNING id",
        (name, email),
    )
    return cur.fetchone()["id"]


def _already_ingested(cur, table: str, source_record_id: str) -> bool:
    cur.execute(f"SELECT 1 FROM {table} WHERE source_record_id = %s", (source_record_id,))
    return cur.fetchone() is not None


def _log_sync(cur, source_type: str, records_processed: int, status: str):
    cur.execute(
        """
        INSERT INTO sync_logs (source_type, last_synced_at, records_processed, status)
        VALUES (%s, %s, %s, %s)
        """,
        (source_type, datetime.now(timezone.utc), records_processed, status),
    )


def _run(source_type: str, endpoint: str, limit: int, handler) -> dict:
    """Generic runner: extract, then hand each record to `handler`, which
    validates/transforms/loads it and returns True if a new row was
    inserted. Always writes a sync_log row, success or failure."""
    try:
        records = fetch(endpoint, limit)
    except Exception as exc:  # network/HTTP failure -> log and move on
        with get_connection() as conn:
            with conn.cursor() as cur:
                _log_sync(cur, source_type, 0, "failed")
        return {"source_type": source_type, "fetched": 0, "inserted": 0, "error": str(exc)}

    inserted = 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            for record in records:
                if handler(cur, record):
                    inserted += 1
            _log_sync(cur, source_type, inserted, "success")

    return {"source_type": source_type, "fetched": len(records), "inserted": inserted}


# ---------------------------------------------------------------------
# Per-source ingestion routines
# ---------------------------------------------------------------------

def ingest_complaints(limit: int = 50) -> dict:
    def handler(cur, r):
        # Validate: required fields present
        if not r.get("description") or not r.get("source_record_id"):
            return False
        # Validate: skip duplicates before touching related tables
        if _already_ingested(cur, "complaints", r["source_record_id"]):
            return False
        product_id = _get_or_create_product(cur, r["product_name"])
        customer_id = _get_or_create_customer(cur, r["customer_name"], r["customer_email"])
        # Transform: trim whitespace on free text
        description = r["description"].strip()
        cur.execute(
            """
            INSERT INTO complaints
                (customer_id, product_id, description, channel, status, source_record_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_record_id) DO NOTHING
            """,
            (
                customer_id,
                product_id,
                description,
                r.get("channel"),
                r.get("status", "open"),
                r["source_record_id"],
                r.get("created_at"),
            ),
        )
        return cur.rowcount > 0

    return _run("complaints", "/org/complaints", limit, handler)


def ingest_warranty_claims(limit: int = 50) -> dict:
    def handler(cur, r):
        if not r.get("source_record_id"):
            return False
        if _already_ingested(cur, "warranty_claims", r["source_record_id"]):
            return False
        product_id = _get_or_create_product(cur, r["product_name"])
        customer_id = _get_or_create_customer(cur, r["customer_name"], r["customer_email"])
        cur.execute(
            """
            INSERT INTO warranty_claims
                (customer_id, product_id, claim_date, status, cost, source_record_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_record_id) DO NOTHING
            """,
            (customer_id, product_id, r.get("claim_date"), r.get("status"), r.get("cost"), r["source_record_id"]),
        )
        return cur.rowcount > 0

    return _run("warranty_claims", "/org/warranty-claims", limit, handler)


def ingest_service_records(limit: int = 50) -> dict:
    def handler(cur, r):
        if not r.get("source_record_id"):
            return False
        if _already_ingested(cur, "service_records", r["source_record_id"]):
            return False
        product_id = _get_or_create_product(cur, r["product_name"])
        cur.execute(
            """
            INSERT INTO service_records
                (product_id, service_date, description, technician_notes, source_record_id)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (source_record_id) DO NOTHING
            """,
            (product_id, r.get("service_date"), r.get("description"), r.get("technician_notes"), r["source_record_id"]),
        )
        return cur.rowcount > 0

    return _run("service_records", "/org/service-records", limit, handler)


def ingest_product_returns(limit: int = 50) -> dict:
    def handler(cur, r):
        if not r.get("source_record_id"):
            return False
        if _already_ingested(cur, "product_returns", r["source_record_id"]):
            return False
        product_id = _get_or_create_product(cur, r["product_name"])
        customer_id = _get_or_create_customer(cur, r["customer_name"], r["customer_email"])
        cur.execute(
            """
            INSERT INTO product_returns
                (customer_id, product_id, return_date, reason, source_record_id)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (source_record_id) DO NOTHING
            """,
            (customer_id, product_id, r.get("return_date"), r.get("reason"), r["source_record_id"]),
        )
        return cur.rowcount > 0

    return _run("product_returns", "/org/product-returns", limit, handler)


def ingest_failures(limit: int = 50) -> dict:
    def handler(cur, r):
        if not r.get("source_record_id"):
            return False
        if _already_ingested(cur, "failures", r["source_record_id"]):
            return False
        product_id = _get_or_create_product(cur, r["product_name"])

        # Resolve the linked complaint (if any) to OUR complaint id.
        complaint_id = None
        linked_source_id = r.get("complaint_source_record_id")
        if linked_source_id:
            cur.execute(
                "SELECT id FROM complaints WHERE source_record_id = %s",
                (linked_source_id,),
            )
            row = cur.fetchone()
            if row:
                complaint_id = row["id"]

        cur.execute(
            """
            INSERT INTO failures
                (product_id, complaint_id, failure_date, description, source_record_id)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (source_record_id) DO NOTHING
            """,
            (product_id, complaint_id, r.get("failure_date"), r.get("description"), r["source_record_id"]),
        )
        return cur.rowcount > 0

    return _run("failures", "/org/failures", limit, handler)


def run_all(limit: int = 50) -> list[dict]:
    """Runs every ingestion routine in sequence and returns a summary
    per source. Used by both the CLI script and (later) a scheduled job."""
    routines = [
        ingest_complaints,
        ingest_warranty_claims,
        ingest_service_records,
        ingest_product_returns,
        ingest_failures,
    ]
    return [routine(limit) for routine in routines]
