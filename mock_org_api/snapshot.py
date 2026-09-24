"""
Snapshot builder — combines all data sources into ONE snapshot for the dashboard.
Simulated NLP: uses symptom patterns to derive sentiment, severity, and predictions.
"""

import random
from datetime import datetime, timedelta
from collections import Counter, defaultdict

from data_generator import (
    generate_complaints,
    generate_failures,
    generate_warranty_claims,
    generate_service_records,
    generate_product_returns,
    SYMPTOM_PATTERNS,
    PRODUCTS,
)

# ---------------------------------------------------------------------
# Simulated NLP mappings
# Each symptom pattern has a realistic sentiment/severity profile.
# This is derived from the signal already in data_generator.py.
# ---------------------------------------------------------------------
SYMPTOM_PROFILE = {
    "noise_and_stops":      {"sentiment": "Negative", "severity": "High"},
    "not_cooling_heating":  {"sentiment": "Negative", "severity": "High"},
    "strange_smell":        {"sentiment": "Negative", "severity": "Critical"},
    "vibration":            {"sentiment": "Negative", "severity": "Medium"},
    "stopped_completely":   {"sentiment": "Negative", "severity": "Critical"},
    "water_leak":           {"sentiment": "Negative", "severity": "High"},
    "error_code":           {"sentiment": "Neutral",  "severity": "Medium"},
    "slow_cycle":           {"sentiment": "Neutral",  "severity": "Low"},
}

# Map failure causes to their likely component
CAUSE_TO_COMPONENT = {
    "Motor bearing failure":    "Motor",
    "Drum imbalance":           "Drum",
    "Motor controller fault":   "Motor Controller",
    "Compressor overheating":   "Compressor",
    "Refrigerant leak":         "Refrigerant System",
    "Thermostat fault":         "Thermostat",
    "Electrical short circuit": "Electrical System",
    "Overheating component":    "Heating Element",
    "Burnt wiring":             "Wiring Harness",
    "Loose mounting":           "Mounting Frame",
    "Software fault":           "Control Board",
    "Water pump failure":       "Water Pump",
    "Seal/gasket failure":      "Seals",
    "Sensor malfunction":       "Sensor",
}

# Human-readable symptom labels for the dashboard
SYMPTOM_LABELS = {
    "noise_and_stops":      "Loud noise + stops",
    "not_cooling_heating":  "Not cooling / heating",
    "strange_smell":        "Strange smell",
    "vibration":            "Excessive vibration",
    "stopped_completely":   "Stopped completely",
    "water_leak":           "Water leakage",
    "error_code":           "Error code on display",
    "slow_cycle":           "Slow cycle time",
}


def _build_complaint_analysis(complaints):
    """Attach simulated NLP output to each complaint."""
    analyzed = []
    for c in complaints:
        # Match description back to a symptom pattern
        symptom_key = None
        for key, pattern in SYMPTOM_PATTERNS.items():
            template_start = pattern["template"].split("{")[0].strip()
            if template_start in c["description"]:
                symptom_key = key
                break
        if symptom_key is None:
            symptom_key = random.choice(list(SYMPTOM_PATTERNS.keys()))

        profile = SYMPTOM_PROFILE[symptom_key]
        analyzed.append({
            **c,
            "symptom_key": symptom_key,
            "symptom_label": SYMPTOM_LABELS[symptom_key],
            "sentiment": profile["sentiment"],
            "severity": profile["severity"],
        })
    return analyzed


def _build_symptom_distribution(analyzed_complaints):
    counter = Counter(c["symptom_label"] for c in analyzed_complaints)
    return dict(counter.most_common())


def _build_sentiment_distribution(analyzed_complaints):
    counter = Counter(c["sentiment"] for c in analyzed_complaints)
    # Ensure all keys present
    for k in ["Positive", "Neutral", "Negative"]:
        counter.setdefault(k, 0)
    return dict(counter)


def _build_severity_distribution(analyzed_complaints):
    counter = Counter(c["severity"] for c in analyzed_complaints)
    for k in ["Critical", "High", "Medium", "Low"]:
        counter.setdefault(k, 0)
    return dict(counter)


def _build_symptom_component_matrix(analyzed_complaints):
    """
    For each symptom, count which components the linked failures point to.
    Uses the failure.complaint_source_record_id link when available.
    """
    # Build complaint_id -> symptom_label map
    complaint_symptom = {
        c["source_record_id"]: c["symptom_label"]
        for c in analyzed_complaints
    }

    matrix = defaultdict(lambda: defaultdict(int))

    failures = generate_failures(limit=300)
    for f in failures:
        linked = f.get("complaint_source_record_id")
        if not linked or linked not in complaint_symptom:
            continue
        symptom_label = complaint_symptom[linked]
        component = CAUSE_TO_COMPONENT.get(f["description"], "Other")
        matrix[symptom_label][component] += 1

    # If matrix is empty (no failures linked yet), seed with expected weights
    if not matrix:
        for symptom_key, pattern in SYMPTOM_PATTERNS.items():
            label = SYMPTOM_LABELS[symptom_key]
            for cause, weight in pattern["causes"]:
                component = CAUSE_TO_COMPONENT.get(cause, "Other")
                matrix[label][component] += int(weight * 100)

    return {k: dict(v) for k, v in matrix.items()}


def _build_predictions(analyzed_complaints):
    """
    Predict which components are most at risk.
    Aggregates symptom frequencies × cause probabilities → component scores.
    """
    component_scores = defaultdict(float)

    for c in analyzed_complaints:
        key = c["symptom_key"]
        pattern = SYMPTOM_PATTERNS[key]
        for cause, weight in pattern["causes"]:
            component = CAUSE_TO_COMPONENT.get(cause, "Other")
            component_scores[component] += weight

    # Sort and label risk levels
    sorted_components = sorted(component_scores.items(), key=lambda x: -x[1])
    max_score = sorted_components[0][1] if sorted_components else 1

    predictions = []
    for component, score in sorted_components[:6]:
        ratio = score / max_score if max_score else 0
        if ratio >= 0.75:
            risk = "High"; confidence = "High"
        elif ratio >= 0.45:
            risk = "Medium"; confidence = "Medium"
        else:
            risk = "Low"; confidence = "High"
        predictions.append({
            "Component": component,
            "Risk Level": risk,
            "Confidence": confidence,
            "Cases": int(score),
            "Trend": random.choice(["↑", "→", "↓"]),
        })
    return predictions


def _build_alerts(analyzed_complaints):
    """Detect simple anomalies: batches/regions with unusual volume."""
    alerts = []

    # Alert 1: product with most Critical severity complaints
    critical_by_product = Counter(
        c["product_name"] for c in analyzed_complaints if c["severity"] == "Critical"
    )
    if critical_by_product:
        top_product, count = critical_by_product.most_common(1)[0]
        if count >= 3:
            alerts.append({
                "title": f"{top_product} — Critical severity cluster",
                "desc": f"{count} critical-severity feedback records linked to this product in the current snapshot."
            })

    # Alert 2: symptom with sharpest spike
    symptom_counts = Counter(c["symptom_label"] for c in analyzed_complaints)
    if symptom_counts:
        top_symptom, count = symptom_counts.most_common(1)[0]
        alerts.append({
            "title": f"Rising symptom: {top_symptom}",
            "desc": f"{count} feedback records reported this symptom. Flagged for engineering review."
        })

    return alerts[:3]


def _build_daily_volume(analyzed_complaints, days=14):
    """Group complaints by day for the last N days."""
    today = datetime.utcnow().date()
    buckets = {(today - timedelta(days=i)): 0 for i in range(days - 1, -1, -1)}

    for c in analyzed_complaints:
        try:
            d = datetime.fromisoformat(c["created_at"]).date()
        except Exception:
            continue
        if d in buckets:
            buckets[d] += 1

    dates = [d.strftime("%d %b") for d in buckets.keys()]
    counts = list(buckets.values())

    # If sparse (mock dates spread over 90 days), inject realistic baseline
    if sum(counts) < days * 2:
        counts = [random.randint(35, 60) for _ in range(days)]

    return {"dates": dates, "counts": counts}


def _build_pipeline_stats(analyzed_complaints):
    raw = len(analyzed_complaints)
    symptoms_extracted = sum(len(c["symptom_label"]) for c in analyzed_complaints) * 2
    return {
        "raw": raw,
        "cleaned": raw,
        "extracted": symptoms_extracted,
        "sentiment": raw,
        "predicted": int(raw * 0.68),
        "stored": raw,
        "duration": f"{random.randint(3, 6)} min {random.randint(10, 59)} sec",
    }


def _build_evidence(analyzed_complaints):
    """Generate a single explainable-AI evidence block."""
    top_symptom = Counter(c["symptom_label"] for c in analyzed_complaints).most_common(1)[0][0]
    pattern = next(
        (SYMPTOM_PATTERNS[k] for k, v in SYMPTOM_LABELS.items() if v == top_symptom),
        list(SYMPTOM_PATTERNS.values())[0]
    )
    top_cause, top_weight = pattern["causes"][0]
    component = CAUSE_TO_COMPONENT.get(top_cause, "Unknown")

    return {
        "prediction": f"{component} failure",
        "historical": f"Historical cases with '{top_symptom}' most often resulted in {top_cause}.",
        "factors": [
            (SYMPTOM_LABELS[k], round(w, 2))
            for k, (_, w) in zip(
                list(SYMPTOM_PATTERNS.keys())[:3],
                [("", p["causes"][0][1]) for p in list(SYMPTOM_PATTERNS.values())[:3]]
            )
        ],
        "recommendation": f"Inspect {component} units flagged in the current snapshot.",
    }


# ---------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------
def build_snapshot():
    """
    Build the full dashboard snapshot.
    Call this from /org/snapshot endpoint.
    """
    now = datetime.utcnow()
    snapshot_time = now.replace(hour=6, minute=0, second=0, microsecond=0)
    next_snapshot = snapshot_time + timedelta(days=1)

    complaints = generate_complaints(limit=200)
    analyzed = _build_complaint_analysis(complaints)

    snapshot = {
        "snapshot_date": snapshot_time.strftime("%d %B %Y, %H:%M EAT"),
        "next_snapshot": next_snapshot.strftime("%d %B %Y, %H:%M EAT"),
        "total_feedback": len(analyzed),
        "daily": _build_daily_volume(analyzed),
        "pipeline": _build_pipeline_stats(analyzed),
        "symptoms": _build_symptom_distribution(analyzed),
        "sentiment": _build_sentiment_distribution(analyzed),
        "severity": _build_severity_distribution(analyzed),
        "symptom_component": _build_symptom_component_matrix(analyzed),
        "predictions": _build_predictions(analyzed),
        "alerts": _build_alerts(analyzed),
        "evidence": _build_evidence(analyzed),
    }
    return snapshot