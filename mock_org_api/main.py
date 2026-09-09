from fastapi import FastAPI, Query

from data_generator import (
    generate_complaints,
    generate_failures,
    generate_product_returns,
    generate_service_records,
    generate_warranty_claims,
)

app = FastAPI(
    title="Mock Organization API",
    description="Simulates the organization's real system until we get access to it.",
)


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


@app.get("/health")
def health():
    return {"status": "ok"}
