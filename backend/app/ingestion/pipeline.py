
"""
ETL Pipeline

Extract -> Validate -> Transform -> Load -> Log

The pipeline retrieves data from the organization's system
(currently the mock organization API), cleans and validates it,
removes duplicates, and loads it into PostgreSQL.
"""

from datetime import datetime, timezone

from app.db.database import get_connection
from app.ingestion.client import fetch


# ---------------------------------------------------------------------
# Cleaning / Transformation helpers
# ---------------------------------------------------------------------

def clean_text(value):
    """Clean text values before storing them."""
    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    # Replace repeated spaces/newlines with a single space
    return " ".join(value.split())


def clean_email(value):
    """Normalize an email address."""
    if value is None:
        return None

    value = str(value).strip().lower()

    return value if value else None


def clean_name(value):
    """Clean and normalize a person's name."""
    if value is None:
        return None

    value = " ".join(str(value).strip().split())

    return value if value else None


# ---------------------------------------------------------------------
# Shared database helpers
# ---------------------------------------------------------------------

def _get_or_create_product(cur, name: str) -> int:
    """Find a product or create it if it does not already exist."""

    name = clean_text(name)

    if not name:
        raise ValueError("Product name is required")

    cur.execute(
        "SELECT id FROM products WHERE name = %s",
        (name,)
    )

    row = cur.fetchone()

    if row:
        return row["id"]

    cur.execute(
        """
        INSERT INTO products (name, category)
        VALUES (%s, %s)
        RETURNING id
        """,
        (name, "unspecified")
    )

    return cur.fetchone()["id"]


def _get_or_create_customer(cur, name: str, email: str) -> int:
    """Find a customer by email or create the customer."""

    # Clean customer information before storing it
    name = clean_name(name)
    email = clean_email(email)

    if not name or not email:
        raise ValueError("Customer name and email are required")

    cur.execute(
        "SELECT id FROM customers WHERE email = %s",
        (email,)
    )

    row = cur.fetchone()

    if row:
        return row["id"]

    cur.execute(
        """
        INSERT INTO customers (full_name, email)
        VALUES (%s, %s)
        RETURNING id
        """,
        (name, email)
    )

    return cur.fetchone()["id"]


def _already_ingested(cur, table: str, source_record_id: str) -> bool:
    """Check whether a source record has already been loaded."""

    cur.execute(
        f"SELECT 1 FROM {table} WHERE source_record_id = %s",
        (source_record_id,)
    )

    return cur.fetchone() is not None


def _log_sync(
    cur,
    source_type: str,
    records_processed: int,
    status: str
):
    """Record the result of an ingestion run."""

    cur.execute(
        """
        INSERT INTO sync_logs
            (source_type, last_synced_at, records_processed, status)
        VALUES (%s, %s, %s, %s)
        """,
        (
            source_type,
            datetime.now(timezone.utc),
            records_processed,
            status
        )
    )


# ---------------------------------------------------------------------
# Generic ingestion runner
# ---------------------------------------------------------------------

def _run(
    source_type: str,
    endpoint: str,
    limit: int,
    handler
) -> dict:
    """
    Generic ingestion runner.

    Steps:
        1. Extract records from the organization API.
        2. Process each record using the source handler.
        3. Count newly inserted records.
        4. Write a synchronization log.
    """

    try:
        records = fetch(endpoint, limit)

    except Exception as exc:
        # Network or HTTP error
        with get_connection() as conn:
            with conn.cursor() as cur:
                _log_sync(
                    cur,
                    source_type,
                    0,
                    "failed"
                )

        return {
            "source_type": source_type,
            "fetched": 0,
            "inserted": 0,
            "error": str(exc)
        }

    inserted = 0

    with get_connection() as conn:
        with conn.cursor() as cur:

            for record in records:
                if handler(cur, record):
                    inserted += 1

            _log_sync(
                cur,
                source_type,
                inserted,
                "success"
            )

    return {
        "source_type": source_type,
        "fetched": len(records),
        "inserted": inserted
    }


# ---------------------------------------------------------------------
# Complaints
# ---------------------------------------------------------------------

def ingest_complaints(limit: int = 50) -> dict:

    def handler(cur, r):

        # Validate required fields
        if not r.get("description"):
            return False

        if not r.get("source_record_id"):
            return False

        # Check for duplicates
        if _already_ingested(
            cur,
            "complaints",
            r["source_record_id"]
        ):
            return False

        # Find/create related product
        product_id = _get_or_create_product(
            cur,
            r.get("product_name")
        )

        # Find/create related customer
        customer_id = _get_or_create_customer(
            cur,
            r.get("customer_name"),
            r.get("customer_email")
        )

        # Transform / clean complaint text
        description = clean_text(
            r.get("description")
        )

        cur.execute(
            """
            INSERT INTO complaints
                (
                    customer_id,
                    product_id,
                    description,
                    channel,
                    status,
                    source_record_id,
                    created_at
                )
            VALUES (%s, %s, %s, %s, %s, %s, %s)

            ON CONFLICT (source_record_id)
            DO NOTHING
            """,
            (
                customer_id,
                product_id,
                description,
                r.get("channel"),
                r.get("status", "open"),
                r["source_record_id"],
                r.get("created_at")
            )
        )

        return cur.rowcount > 0

    return _run(
        "complaints",
        "/org/complaints",
        limit,
        handler
    )


# ---------------------------------------------------------------------
# Warranty claims
# ---------------------------------------------------------------------

def ingest_warranty_claims(limit: int = 50) -> dict:

    def handler(cur, r):

        # Validate required field
        if not r.get("source_record_id"):
            return False

        # Check for duplicates
        if _already_ingested(
            cur,
            "warranty_claims",
            r["source_record_id"]
        ):
            return False

        product_id = _get_or_create_product(
            cur,
            r.get("product_name")
        )

        customer_id = _get_or_create_customer(
            cur,
            r.get("customer_name"),
            r.get("customer_email")
        )

        cur.execute(
            """
            INSERT INTO warranty_claims
                (
                    customer_id,
                    product_id,
                    claim_date,
                    status,
                    cost,
                    source_record_id
                )
            VALUES (%s, %s, %s, %s, %s, %s)

            ON CONFLICT (source_record_id)
            DO NOTHING
            """,
            (
                customer_id,
                product_id,
                r.get("claim_date"),
                r.get("status"),
                r.get("cost"),
                r["source_record_id"]
            )
        )

        return cur.rowcount > 0

    return _run(
        "warranty_claims",
        "/org/warranty-claims",
        limit,
        handler
    )


# ---------------------------------------------------------------------
# Service records
# ---------------------------------------------------------------------

def ingest_service_records(limit: int = 50) -> dict:

    def handler(cur, r):

        # Validate required field
        if not r.get("source_record_id"):
            return False

        # Check for duplicates
        if _already_ingested(
            cur,
            "service_records",
            r["source_record_id"]
        ):
            return False

        product_id = _get_or_create_product(
            cur,
            r.get("product_name")
        )

        # Clean service text
        description = clean_text(
            r.get("description")
        )

        technician_notes = clean_text(
            r.get("technician_notes")
        )

        cur.execute(
            """
            INSERT INTO service_records
                (
                    product_id,
                    service_date,
                    description,
                    technician_notes,
                    source_record_id
                )
            VALUES (%s, %s, %s, %s, %s)

            ON CONFLICT (source_record_id)
            DO NOTHING
            """,
            (
                product_id,
                r.get("service_date"),
                description,
                technician_notes,
                r["source_record_id"]
            )
        )

        return cur.rowcount > 0

    return _run(
        "service_records",
        "/org/service-records",
        limit,
        handler
    )


# ---------------------------------------------------------------------
# Product returns
# ---------------------------------------------------------------------

def ingest_product_returns(limit: int = 50) -> dict:

    def handler(cur, r):

        # Validate required field
        if not r.get("source_record_id"):
            return False

        # Check for duplicates
        if _already_ingested(
            cur,
            "product_returns",
            r["source_record_id"]
        ):
            return False

        product_id = _get_or_create_product(
            cur,
            r.get("product_name")
        )

        customer_id = _get_or_create_customer(
            cur,
            r.get("customer_name"),
            r.get("customer_email")
        )

        # Clean return reason
        reason = clean_text(
            r.get("reason")
        )

        cur.execute(
            """
            INSERT INTO product_returns
                (
                    customer_id,
                    product_id,
                    return_date,
                    reason,
                    source_record_id
                )
            VALUES (%s, %s, %s, %s, %s)

            ON CONFLICT (source_record_id)
            DO NOTHING
            """,
            (
                customer_id,
                product_id,
                r.get("return_date"),
                reason,
                r["source_record_id"]
            )
        )

        return cur.rowcount > 0

    return _run(
        "product_returns",
        "/org/product-returns",
        limit,
        handler
    )


# ---------------------------------------------------------------------
# Failures
# ---------------------------------------------------------------------

def ingest_failures(limit: int = 50) -> dict:

    def handler(cur, r):

        # Validate required field
        if not r.get("source_record_id"):
            return False

        # Check for duplicates
        if _already_ingested(
            cur,
            "failures",
            r["source_record_id"]
        ):
            return False

        product_id = _get_or_create_product(
            cur,
            r.get("product_name")
        )

        # Resolve linked complaint
        # from the organization's source ID
        # to our local complaint ID.
        complaint_id = None

        linked_source_id = r.get(
            "complaint_source_record_id"
        )

        if linked_source_id:

            cur.execute(
                """
                SELECT id
                FROM complaints
                WHERE source_record_id = %s
                """,
                (linked_source_id,)
            )

            row = cur.fetchone()

            if row:
                complaint_id = row["id"]

        # Clean failure description
        description = clean_text(
            r.get("description")
        )

        cur.execute(
            """
            INSERT INTO failures
                (
                    product_id,
                    complaint_id,
                    failure_date,
                    description,
                    source_record_id
                )
            VALUES (%s, %s, %s, %s, %s)

            ON CONFLICT (source_record_id)
            DO NOTHING
            """,
            (
                product_id,
                complaint_id,
                r.get("failure_date"),
                description,
                r["source_record_id"]
            )
        )

        return cur.rowcount > 0

    return _run(
        "failures",
        "/org/failures",
        limit,
        handler
    )


# ---------------------------------------------------------------------
# Run all ingestion routines
# ---------------------------------------------------------------------

def run_all(limit: int = 50) -> list[dict]:
    """
    Run every ingestion routine in sequence.

    Used by the CLI script and later by
    scheduled ingestion jobs.
    """

    routines = [
        ingest_complaints,
        ingest_warranty_claims,
        ingest_service_records,
        ingest_product_returns,
        ingest_failures
    ]

    return [
        routine(limit)
        for routine in routines
    ]

