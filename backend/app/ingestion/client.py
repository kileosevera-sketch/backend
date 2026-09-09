import os

import httpx

# Points at the mock organization API for now. When real access is
# granted, only this URL (and auth, if the real API needs it) changes —
# nothing else in the ingestion pipeline does.
ORG_API_BASE_URL = os.getenv("ORG_API_BASE_URL", "http://localhost:8001")


def fetch(endpoint: str, limit: int = 50) -> list[dict]:
    """Extract step: pulls raw records from the organization system."""
    url = f"{ORG_API_BASE_URL}{endpoint}"
    response = httpx.get(url, params={"limit": limit}, timeout=15)
    response.raise_for_status()
    return response.json()
