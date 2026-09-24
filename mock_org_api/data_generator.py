import random
from datetime import datetime, timedelta

from faker import Faker

fake = Faker()

PRODUCTS = [
    {"id": 1, "name": "Washing Machine X200"},
    {"id": 2, "name": "Refrigerator R-200"},
    {"id": 3, "name": "Microwave M-50"},
    {"id": 4, "name": "Air Conditioner AC-1000"},
    {"id": 5, "name": "Water Heater WH-30"},
]

CHANNELS = ["call_centre", "feedback_form", "email", "in_store"]
STATUSES = ["open", "in_progress", "resolved"]

# --------------------------------------------------------------------
# Symptom <-> failure cause correlations.
#
# Each symptom pattern maps to a set of realistic failure causes with
# assigned probabilities. This is what gives the mock data a genuine
# signal to analyze later -- e.g. "noise + stops" complaints really
# are followed by "Motor bearing failure" about 70% of the time in
# this simulated dataset, so a co-occurrence/prediction step built on
# top of this data has something real to recover.
#
# Tune LINK_TO_COMPLAINT_PROBABILITY or the per-symptom probabilities
# below if you want a stronger/weaker signal.
# --------------------------------------------------------------------
LINK_TO_COMPLAINT_PROBABILITY = 0.7

SYMPTOM_PATTERNS = {
    "noise_and_stops": {
        "template": "My {product} makes a loud noise during operation and sometimes stops.",
        "causes": [
            ("Motor bearing failure", 0.70),
            ("Drum imbalance", 0.20),
            ("Motor controller fault", 0.10),
        ],
    },
    "not_cooling_heating": {
        "template": "The {product} is not cooling/heating properly anymore.",
        "causes": [
            ("Compressor overheating", 0.65),
            ("Refrigerant leak", 0.25),
            ("Thermostat fault", 0.10),
        ],
    },
    "strange_smell": {
        "template": "There is a strange smell coming from the {product}.",
        "causes": [
            ("Electrical short circuit", 0.60),
            ("Overheating component", 0.30),
            ("Burnt wiring", 0.10),
        ],
    },
    "vibration": {
        "template": "The {product} vibrates a lot and shakes the whole room.",
        "causes": [
            ("Drum imbalance", 0.55),
            ("Loose mounting", 0.30),
            ("Motor bearing failure", 0.15),
        ],
    },
    "stopped_completely": {
        "template": "The {product} stopped working completely after two months.",
        "causes": [
            ("Software fault", 0.45),
            ("Electrical short circuit", 0.35),
            ("Motor controller fault", 0.20),
        ],
    },
    "water_leak": {
        "template": "Water is leaking from the {product}.",
        "causes": [
            ("Water pump failure", 0.75),
            ("Seal/gasket failure", 0.25),
        ],
    },
    "error_code": {
        "template": "The {product} display shows an error code and won't reset.",
        "causes": [
            ("Software fault", 0.60),
            ("Sensor malfunction", 0.40),
        ],
    },
    "slow_cycle": {
        "template": "The {product} takes much longer than usual to complete a cycle.",
        "causes": [
            ("Sensor malfunction", 0.50),
            ("Software fault", 0.30),
            ("Motor controller fault", 0.20),
        ],
    },
}

# Fallback cause pool for failures NOT linked to any recent complaint
# (e.g. found during routine service inspection rather than reported).
_ALL_CAUSES = sorted({cause for p in SYMPTOM_PATTERNS.values() for cause, _ in p["causes"]})

# In-memory "recent complaints" list. Lets /org/failures correlate a
# failure back to a complaint's symptom pattern when both endpoints
# are called against the same running mock API process (which is how
# the ingestion pipeline uses it). Resets when the server restarts --
# that's fine, it's simulated data, not a real database.
_recent_complaints: list[dict] = []
_MAX_RECENT = 300


def _remember_complaint(source_record_id, product_id, product_name, symptom_key):
    _recent_complaints.append(
        {
            "source_record_id": source_record_id,
            "product_id": product_id,
            "product_name": product_name,
            "symptom_key": symptom_key,
        }
    )
    if len(_recent_complaints) > _MAX_RECENT:
        del _recent_complaints[: len(_recent_complaints) - _MAX_RECENT]


def _weighted_choice(rng: random.Random, options: list[tuple[str, float]]) -> str:
    total = sum(weight for _, weight in options)
    r = rng.uniform(0, total)
    upto = 0.0
    for value, weight in options:
        upto += weight
        if upto >= r:
            return value
    return options[-1][0]


def _random_date(days_back=90):
    dt = datetime.utcnow() - timedelta(
        days=random.randint(0, days_back), hours=random.randint(0, 23)
    )
    return dt.isoformat()


def generate_complaints(limit=50):
    results = []
    for i in range(limit):
        source_record_id = f"CMP-{10000 + i}"
        # Seeded per-record RNG: same source_record_id always produces
        # the same product/symptom/channel/status, even across separate
        # calls to this endpoint. Needed so failures generated later
        # (possibly in a different request) stay consistent with what
        # was actually ingested for this complaint.
        rng = random.Random(source_record_id)

        product = rng.choice(PRODUCTS)
        symptom_key = rng.choice(list(SYMPTOM_PATTERNS.keys()))
        pattern = SYMPTOM_PATTERNS[symptom_key]

        record = {
            "source_record_id": source_record_id,
            "customer_name": fake.name(),
            "customer_email": fake.email(),
            "product_id": product["id"],
            "product_name": product["name"],
            "description": pattern["template"].format(product=product["name"]),
            "channel": rng.choice(CHANNELS),
            "status": rng.choice(STATUSES),
            "created_at": _random_date(),
        }
        _remember_complaint(source_record_id, product["id"], product["name"], symptom_key)
        results.append(record)
    return results


def generate_warranty_claims(limit=50):
    results = []
    for i in range(limit):
        product = random.choice(PRODUCTS)
        results.append(
            {
                "source_record_id": f"WAR-{20000 + i}",
                "customer_name": fake.name(),
                "customer_email": fake.email(),
                "product_id": product["id"],
                "product_name": product["name"],
                "claim_date": _random_date(),
                "status": random.choice(["approved", "pending", "rejected"]),
                "cost": round(random.uniform(20, 500), 2),
            }
        )
    return results


def generate_service_records(limit=50):
    results = []
    for i in range(limit):
        product = random.choice(PRODUCTS)
        results.append(
            {
                "source_record_id": f"SVC-{30000 + i}",
                "product_id": product["id"],
                "product_name": product["name"],
                "service_date": _random_date(),
                "description": fake.sentence(nb_words=8),
                "technician_notes": fake.sentence(nb_words=12),
            }
        )
    return results


def generate_product_returns(limit=50):
    results = []
    for i in range(limit):
        product = random.choice(PRODUCTS)
        results.append(
            {
                "source_record_id": f"RET-{40000 + i}",
                "customer_name": fake.name(),
                "customer_email": fake.email(),
                "product_id": product["id"],
                "product_name": product["name"],
                "return_date": _random_date(),
                "reason": random.choice(
                    ["defective", "not as described", "changed mind", "wrong item"]
                ),
            }
        )
    return results


def generate_failures(limit=50):
    results = []
    for i in range(limit):
        source_record_id = f"FAIL-{50000 + i}"
        rng = random.Random(source_record_id + "-fail")

        linked_complaint = None
        if _recent_complaints and rng.random() < LINK_TO_COMPLAINT_PROBABILITY:
            linked_complaint = rng.choice(_recent_complaints)

        if linked_complaint:
            product_id = linked_complaint["product_id"]
            product_name = linked_complaint["product_name"]
            pattern = SYMPTOM_PATTERNS[linked_complaint["symptom_key"]]
            description = _weighted_choice(rng, pattern["causes"])
            complaint_source_record_id = linked_complaint["source_record_id"]
        else:
            product = rng.choice(PRODUCTS)
            product_id = product["id"]
            product_name = product["name"]
            description = rng.choice(_ALL_CAUSES)
            complaint_source_record_id = None

        results.append(
            {
                "source_record_id": source_record_id,
                "product_id": product_id,
                "product_name": product_name,
                "failure_date": _random_date(),
                "description": description,
                "complaint_source_record_id": complaint_source_record_id,
            }
        )
    return results


# =====================================================================
# PERSISTENT STATE FOR INCREMENTAL SYNC
# =====================================================================
# These lists accumulate every record ever generated this session.
# The /new endpoints read from them, and /advance-day appends to them.
# In-memory by design — a mock API restart starts fresh, which is fine
# for simulating a day boundary.

_all_complaints: list[dict] = []
_all_warranty_claims: list[dict] = []
_all_service_records: list[dict] = []
_all_product_returns: list[dict] = []
_all_failures: list[dict] = []

_MAX_STORE = 20000

# Global counters so new record IDs never collide with initial ones
_next_complaint_num = 20000
_next_warranty_num = 30000
_next_service_num = 40000
_next_return_num = 50000
_next_failure_num = 60000


def _remember(record: dict, store: list, max_size=_MAX_STORE):
    store.append(record)
    if len(store) > max_size:
        del store[: len(store) - max_size]


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


# ---------------------------------------------------------------------
# Initial pull — populates the persistent store on first call.
# ---------------------------------------------------------------------
def _ensure_initial_store():
    """Call once to seed the store with the standard 200 records."""
    if _all_complaints:
        return
    _all_complaints.extend(generate_complaints(200))
    _all_warranty_claims.extend(generate_warranty_claims(200))
    _all_service_records.extend(generate_service_records(200))
    _all_product_returns.extend(generate_product_returns(200))
    _all_failures.extend(generate_failures(200))


# ---------------------------------------------------------------------
# New record generators — each assigns fresh IDs and timestamps "now"
# ---------------------------------------------------------------------
def generate_new_complaints(count: int) -> list[dict]:
    global _next_complaint_num
    _ensure_initial_store()
    results = []
    for _ in range(count):
        sid = f"CMP-{_next_complaint_num}"
        _next_complaint_num += 1

        rng = random.Random(sid)
        product = rng.choice(PRODUCTS)
        symptom_key = rng.choice(list(SYMPTOM_PATTERNS.keys()))
        pattern = SYMPTOM_PATTERNS[symptom_key]

        record = {
            "source_record_id": sid,
            "customer_name": fake.name(),
            "customer_email": fake.email(),
            "product_id": product["id"],
            "product_name": product["name"],
            "description": pattern["template"].format(product=product["name"]),
            "channel": rng.choice(CHANNELS),
            "status": rng.choice(STATUSES),
            "created_at": _now_iso(),
        }
        _remember_complaint(sid, product["id"], product["name"], symptom_key)
        _remember(record, _all_complaints)
        results.append(record)
    return results


def generate_new_warranty_claims(count: int) -> list[dict]:
    global _next_warranty_num
    _ensure_initial_store()
    results = []
    for _ in range(count):
        sid = f"WAR-{_next_warranty_num}"
        _next_warranty_num += 1
        product = random.choice(PRODUCTS)
        record = {
            "source_record_id": sid,
            "customer_name": fake.name(),
            "customer_email": fake.email(),
            "product_id": product["id"],
            "product_name": product["name"],
            "claim_date": _now_iso(),
            "status": random.choice(["approved", "pending", "rejected"]),
            "cost": round(random.uniform(20, 500), 2),
        }
        _remember(record, _all_warranty_claims)
        results.append(record)
    return results


def generate_new_service_records(count: int) -> list[dict]:
    global _next_service_num
    _ensure_initial_store()
    results = []
    for _ in range(count):
        sid = f"SVC-{_next_service_num}"
        _next_service_num += 1
        product = random.choice(PRODUCTS)
        record = {
            "source_record_id": sid,
            "product_id": product["id"],
            "product_name": product["name"],
            "service_date": _now_iso(),
            "description": fake.sentence(nb_words=8),
            "technician_notes": fake.sentence(nb_words=12),
        }
        _remember(record, _all_service_records)
        results.append(record)
    return results


def generate_new_product_returns(count: int) -> list[dict]:
    global _next_return_num
    _ensure_initial_store()
    results = []
    for _ in range(count):
        sid = f"RET-{_next_return_num}"
        _next_return_num += 1
        product = random.choice(PRODUCTS)
        record = {
            "source_record_id": sid,
            "customer_name": fake.name(),
            "customer_email": fake.email(),
            "product_id": product["id"],
            "product_name": product["name"],
            "return_date": _now_iso(),
            "reason": random.choice(
                ["defective", "not as described", "changed mind", "wrong item"]
            ),
        }
        _remember(record, _all_product_returns)
        results.append(record)
    return results


def generate_new_failures(count: int) -> list[dict]:
    global _next_failure_num
    _ensure_initial_store()
    results = []
    for _ in range(count):
        sid = f"FAIL-{_next_failure_num}"
        _next_failure_num += 1

        rng = random.Random(sid + "-fail")
        linked_complaint = None
        if _recent_complaints and rng.random() < LINK_TO_COMPLAINT_PROBABILITY:
            linked_complaint = rng.choice(_recent_complaints)

        if linked_complaint:
            product_id = linked_complaint["product_id"]
            product_name = linked_complaint["product_name"]
            pattern = SYMPTOM_PATTERNS[linked_complaint["symptom_key"]]
            description = _weighted_choice(rng, pattern["causes"])
            complaint_sid = linked_complaint["source_record_id"]
        else:
            product = rng.choice(PRODUCTS)
            product_id = product["id"]
            product_name = product["name"]
            description = rng.choice(_ALL_CAUSES)
            complaint_sid = None

        record = {
            "source_record_id": sid,
            "product_id": product_id,
            "product_name": product_name,
            "failure_date": _now_iso(),
            "description": description,
            "complaint_source_record_id": complaint_sid,
        }
        _remember(record, _all_failures)
        results.append(record)
    return results

# ---------------------------------------------------------------------
# Filter helpers — return records created after a given timestamp
# ---------------------------------------------------------------------
def _since(store: list, since_iso: str) -> list[dict]:
    _ensure_initial_store()
    try:
        since_dt = datetime.fromisoformat(since_iso)
    except Exception:
        return store[:]
    return [
        r for r in store
        if datetime.fromisoformat(r.get("created_at") or r.get("claim_date") or r.get("service_date") or r.get("return_date") or r.get("failure_date")) > since_dt
    ]


def get_complaints_since(since_iso: str) -> list[dict]:
    return _since(_all_complaints, since_iso)


def get_warranty_claims_since(since_iso: str) -> list[dict]:
    return _since(_all_warranty_claims, since_iso)


def get_service_records_since(since_iso: str) -> list[dict]:
    return _since(_all_service_records, since_iso)


def get_product_returns_since(since_iso: str) -> list[dict]:
    return _since(_all_product_returns, since_iso)


def get_failures_since(since_iso: str) -> list[dict]:
    return _since(_all_failures, since_iso)

# =====================================================================
# PERSISTENT STORE INTEGRATION
# =====================================================================
from state_manager import (
    load_state, save_state, append_records, get_records, next_id
)


def _persist_new(store_name: str, records: list[dict]):
    """Append records to the persistent store."""
    append_records(store_name, records)


def generate_new_complaints_persistent(count: int) -> list[dict]:
    """Generate new complaints, persist them, return them."""
    state = load_state()
    results = []
    for _ in range(count):
        sid = f"CMP-{state['next_ids']['complaint']}"
        state["next_ids"]["complaint"] += 1

        rng = random.Random(sid)
        product = rng.choice(PRODUCTS)
        symptom_key = rng.choice(list(SYMPTOM_PATTERNS.keys()))
        pattern = SYMPTOM_PATTERNS[symptom_key]

        record = {
            "source_record_id": sid,
            "customer_name": fake.name(),
            "customer_email": fake.email(),
            "product_id": product["id"],
            "product_name": product["name"],
            "description": pattern["template"].format(product=product["name"]),
            "channel": rng.choice(CHANNELS),
            "status": rng.choice(STATUSES),
            "created_at": datetime.utcnow().isoformat(),
        }
        _remember_complaint(sid, product["id"], product["name"], symptom_key)
        results.append(record)

    state["complaints"].extend(results)
    save_state(state)
    return results


def generate_new_warranty_claims_persistent(count: int) -> list[dict]:
    state = load_state()
    results = []
    for _ in range(count):
        sid = f"WAR-{state['next_ids']['warranty']}"
        state["next_ids"]["warranty"] += 1
        product = random.choice(PRODUCTS)
        results.append({
            "source_record_id": sid,
            "customer_name": fake.name(),
            "customer_email": fake.email(),
            "product_id": product["id"],
            "product_name": product["name"],
            "claim_date": datetime.utcnow().isoformat(),
            "status": random.choice(["approved", "pending", "rejected"]),
            "cost": round(random.uniform(20, 500), 2),
        })
    state["warranty_claims"].extend(results)
    save_state(state)
    return results


# Similar for service_records, product_returns, failures
def generate_new_service_records_persistent(count: int) -> list[dict]:
    state = load_state()
    results = []
    for _ in range(count):
        sid = f"SVC-{state['next_ids']['service']}"
        state["next_ids"]["service"] += 1
        product = random.choice(PRODUCTS)
        results.append({
            "source_record_id": sid,
            "product_id": product["id"],
            "product_name": product["name"],
            "service_date": datetime.utcnow().isoformat(),
            "description": fake.sentence(nb_words=8),
            "technician_notes": fake.sentence(nb_words=12),
        })
    state["service_records"].extend(results)
    save_state(state)
    return results


def generate_new_product_returns_persistent(count: int) -> list[dict]:
    state = load_state()
    results = []
    for _ in range(count):
        sid = f"RET-{state['next_ids']['return']}"
        state["next_ids"]["return"] += 1
        product = random.choice(PRODUCTS)
        results.append({
            "source_record_id": sid,
            "customer_name": fake.name(),
            "customer_email": fake.email(),
            "product_id": product["id"],
            "product_name": product["name"],
            "return_date": datetime.utcnow().isoformat(),
            "reason": random.choice(["defective", "not as described", "changed mind", "wrong item"]),
        })
    state["product_returns"].extend(results)
    save_state(state)
    return results


def generate_new_failures_persistent(count: int) -> list[dict]:
    state = load_state()
    results = []
    for _ in range(count):
        sid = f"FAIL-{state['next_ids']['failure']}"
        state["next_ids"]["failure"] += 1

        rng = random.Random(sid + "-fail")
        linked_complaint = None
        if _recent_complaints and rng.random() < LINK_TO_COMPLAINT_PROBABILITY:
            linked_complaint = rng.choice(_recent_complaints)

        if linked_complaint:
            product_id = linked_complaint["product_id"]
            product_name = linked_complaint["product_name"]
            pattern = SYMPTOM_PATTERNS[linked_complaint["symptom_key"]]
            description = _weighted_choice(rng, pattern["causes"])
            complaint_sid = linked_complaint["source_record_id"]
        else:
            product = rng.choice(PRODUCTS)
            product_id = product["id"]
            product_name = product["name"]
            description = rng.choice(_ALL_CAUSES)
            complaint_sid = None

        results.append({
            "source_record_id": sid,
            "product_id": product_id,
            "product_name": product_name,
            "failure_date": datetime.utcnow().isoformat(),
            "description": description,
            "complaint_source_record_id": complaint_sid,
        })
    state["failures"].extend(results)
    save_state(state)
    return results


def get_records_since(store_name: str, since_iso: str) -> list[dict]:
    """Get records from a persistent store created after a given timestamp."""
    records = get_records(store_name)
    try:
        since_dt = datetime.fromisoformat(since_iso)
    except Exception:
        return records

    # Find date field
    date_fields = ["created_at", "claim_date", "service_date", "return_date", "failure_date"]

    result = []
    for r in records:
        for field in date_fields:
            if field in r and r[field]:
                try:
                    if datetime.fromisoformat(r[field]) > since_dt:
                        result.append(r)
                    break
                except Exception:
                    pass
    return result

# =====================================================================
# PERSISTENT STORE INTEGRATION (weekly sync)
# =====================================================================
from state_manager import load_state, save_state, get_records, get_stats


def _persist_new(store_name: str, records: list[dict]):
    state = load_state()
    state[store_name].extend(records)
    save_state(state)


def generate_new_complaints_persistent(count: int) -> list[dict]:
    """Generate new complaints, persist to disk, return them."""
    state = load_state()
    results = []
    for _ in range(count):
        sid = f"CMP-{state['next_ids']['complaint']}"
        state["next_ids"]["complaint"] += 1

        rng = random.Random(sid)
        product = rng.choice(PRODUCTS)
        symptom_key = rng.choice(list(SYMPTOM_PATTERNS.keys()))
        pattern = SYMPTOM_PATTERNS[symptom_key]

        record = {
            "source_record_id": sid,
            "customer_name": fake.name(),
            "customer_email": fake.email(),
            "product_id": product["id"],
            "product_name": product["name"],
            "description": pattern["template"].format(product=product["name"]),
            "channel": rng.choice(CHANNELS),
            "status": rng.choice(STATUSES),
            "created_at": datetime.utcnow().isoformat(),
        }
        _remember_complaint(sid, product["id"], product["name"], symptom_key)
        results.append(record)

    state["complaints"].extend(results)
    save_state(state)
    return results


def generate_new_warranty_claims_persistent(count: int) -> list[dict]:
    state = load_state()
    results = []
    for _ in range(count):
        sid = f"WAR-{state['next_ids']['warranty']}"
        state["next_ids"]["warranty"] += 1
        product = random.choice(PRODUCTS)
        results.append({
            "source_record_id": sid,
            "customer_name": fake.name(),
            "customer_email": fake.email(),
            "product_id": product["id"],
            "product_name": product["name"],
            "claim_date": datetime.utcnow().isoformat(),
            "status": random.choice(["approved", "pending", "rejected"]),
            "cost": round(random.uniform(20, 500), 2),
        })
    state["warranty_claims"].extend(results)
    save_state(state)
    return results


def generate_new_service_records_persistent(count: int) -> list[dict]:
    state = load_state()
    results = []
    for _ in range(count):
        sid = f"SVC-{state['next_ids']['service']}"
        state["next_ids"]["service"] += 1
        product = random.choice(PRODUCTS)
        results.append({
            "source_record_id": sid,
            "product_id": product["id"],
            "product_name": product["name"],
            "service_date": datetime.utcnow().isoformat(),
            "description": fake.sentence(nb_words=8),
            "technician_notes": fake.sentence(nb_words=12),
        })
    state["service_records"].extend(results)
    save_state(state)
    return results


def generate_new_product_returns_persistent(count: int) -> list[dict]:
    state = load_state()
    results = []
    for _ in range(count):
        sid = f"RET-{state['next_ids']['return']}"
        state["next_ids"]["return"] += 1
        product = random.choice(PRODUCTS)
        results.append({
            "source_record_id": sid,
            "customer_name": fake.name(),
            "customer_email": fake.email(),
            "product_id": product["id"],
            "product_name": product["name"],
            "return_date": datetime.utcnow().isoformat(),
            "reason": random.choice(
                ["defective", "not as described", "changed mind", "wrong item"]
            ),
        })
    state["product_returns"].extend(results)
    save_state(state)
    return results


def generate_new_failures_persistent(count: int) -> list[dict]:
    state = load_state()
    results = []
    for _ in range(count):
        sid = f"FAIL-{state['next_ids']['failure']}"
        state["next_ids"]["failure"] += 1

        rng = random.Random(sid + "-fail")
        linked_complaint = None
        if _recent_complaints and rng.random() < LINK_TO_COMPLAINT_PROBABILITY:
            linked_complaint = rng.choice(_recent_complaints)

        if linked_complaint:
            product_id = linked_complaint["product_id"]
            product_name = linked_complaint["product_name"]
            pattern = SYMPTOM_PATTERNS[linked_complaint["symptom_key"]]
            description = _weighted_choice(rng, pattern["causes"])
            complaint_sid = linked_complaint["source_record_id"]
        else:
            product = rng.choice(PRODUCTS)
            product_id = product["id"]
            product_name = product["name"]
            description = rng.choice(_ALL_CAUSES)
            complaint_sid = None

        results.append({
            "source_record_id": sid,
            "product_id": product_id,
            "product_name": product_name,
            "failure_date": datetime.utcnow().isoformat(),
            "description": description,
            "complaint_source_record_id": complaint_sid,
        })
    state["failures"].extend(results)
    save_state(state)
    return results


def get_records_since(store_name: str, since_iso: str) -> list[dict]:
    """Return records from persistent store created after a given timestamp."""
    records = get_records(store_name)
    try:
        since_dt = datetime.fromisoformat(since_iso)
    except Exception:
        return records

    date_fields = ["created_at", "claim_date", "service_date", "return_date", "failure_date"]

    result = []
    for r in records:
        for field in date_fields:
            if field in r and r[field]:
                try:
                    if datetime.fromisoformat(r[field]) > since_dt:
                        result.append(r)
                    break
                except Exception:
                    pass
    return result


def seed_initial_week(records_per_source: int = 350):
    """
    First-time seed — populates the store with the first week of records.
    Called automatically by /advance-week if the store is empty.
    """
    state = load_state()
    if state["complaints"]:
        return  # already seeded

    # Generate the first batch of records with dates spread across the last 7 days
    now = datetime.utcnow()

    # Complaints spread over 7 days
    batch = generate_new_complaints_persistent(records_per_source)
    state = load_state()
    for i, r in enumerate(batch):
        days_ago = 6 - int(i * 6 / max(len(batch), 1))
        r["created_at"] = (now - timedelta(days=days_ago, hours=random.randint(0, 23))).isoformat()
    # Re-save with adjusted dates
    state["complaints"] = [
        r for r in state["complaints"]
        if r["source_record_id"] not in {b["source_record_id"] for b in batch}
    ] + batch
    save_state(state)

    # Other sources — just timestamps
    generate_new_warranty_claims_persistent(records_per_source)
    generate_new_service_records_persistent(records_per_source)
    generate_new_product_returns_persistent(records_per_source)
    generate_new_failures_persistent(records_per_source)