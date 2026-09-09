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
