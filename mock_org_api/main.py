"""
Mock Organization API — with persistent state (mock_state.json).
Restarts don't lose data.
"""

from datetime import datetime
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from data_generator import (
    generate_complaints,
    generate_failures,
    generate_product_returns,
    generate_service_records,
    generate_warranty_claims,
    generate_new_complaints_persistent,
    generate_new_warranty_claims_persistent,
    generate_new_service_records_persistent,
    generate_new_product_returns_persistent,
    generate_new_failures_persistent,
    get_records_since,
    seed_initial_week,
)
from state_manager import load_state, reset_state, get_stats

app = FastAPI(title="Mock Organization API — Persistent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------
# Initial-pull endpoints (kept for compatibility)
# ---------------------------------------------------------------------
@app.get("/org/complaints")
def complaints(limit: int = Query(50, le=500)):
    return generate_complaints(limit)


@app.get("/org/warranty-claims")
def warranty_claims(limit: int = Query(50, le=500)):
    return generate_warranty_claims(limit)


@app.get("/org/service-records")
def service_records(limit: int = Query(50, le=500)):
    return generate_service_records(limit)


@app.get("/org/product-returns")
def product_returns(limit: int = Query(50, le=500)):
    return generate_product_returns(limit)


@app.get("/org/failures")
def failures(limit: int = Query(50, le=500)):
    return generate_failures(limit)


# ---------------------------------------------------------------------
# Incremental endpoints — read from persistent store
# ---------------------------------------------------------------------
@app.get("/org/complaints/new")
def complaints_new(since: str = Query(..., description="ISO timestamp")):
    return get_records_since("complaints", since)


@app.get("/org/warranty-claims/new")
def warranty_claims_new(since: str = Query(...)):
    return get_records_since("warranty_claims", since)


@app.get("/org/service-records/new")
def service_records_new(since: str = Query(...)):
    return get_records_since("service_records", since)


@app.get("/org/product-returns/new")
def product_returns_new(since: str = Query(...)):
    return get_records_since("product_returns", since)


@app.get("/org/failures/new")
def failures_new(since: str = Query(...)):
    return get_records_since("failures", since)


# ---------------------------------------------------------------------
# Weekly simulation
# ---------------------------------------------------------------------
@app.post("/org/advance-week")
def advance_week(records_per_source: int = Query(350, ge=1, le=500)):
    """
    Advance the mock organization by one week.
    If the store is empty, seeds the first week.
    Otherwise, adds a fresh week of records.
    """
    state = load_state()
    if not state["complaints"]:
        seed_initial_week(records_per_source)
        mode = "seeded"
    else:
        generate_new_complaints_persistent(records_per_source)
        generate_new_warranty_claims_persistent(records_per_source)
        generate_new_service_records_persistent(records_per_source)
        generate_new_product_returns_persistent(records_per_source)
        generate_new_failures_persistent(records_per_source)
        mode = "advanced"

    stats = get_stats()
    return {
        "message": f"Mock organization {mode} ({records_per_source} records per source).",
        "mode": mode,
        "added_per_source": records_per_source,
        "totals": stats["counts"],
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/org/reset")
def reset():
    reset_state()
    return {"message": "State reset."}


@app.get("/org/stats")
def stats():
    return get_stats()


@app.get("/health")
def health():
    return {"status": "ok"}