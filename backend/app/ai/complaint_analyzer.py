
import re

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# MODEL VERSION
MODEL_VERSION = "sprint2-v4-vader"


# VADER SENTIMENT ANALYZER
vader_analyzer = SentimentIntensityAnalyzer()

def analyze_sentiment(text):
    """
    Analyze customer complaint sentiment using VADER.

    Returns:
        Positive
        Negative
        Neutral
    """

    scores = vader_analyzer.polarity_scores(text)

    compound_score = scores["compound"]

    if compound_score >= 0.05:
        return "Positive"

    elif compound_score <= -0.05:
        return "Negative"

    else:
        return "Neutral"

# TEXT PREPROCESSING

def preprocess_text(text):
    """
    Clean and normalize complaint text before analysis.
    """

    if not text:
        return ""

    # Convert text to lowercase
    text = text.lower()

    # Remove extra spaces
    text = re.sub(r"\s+", " ", text)

    # Fix known data-quality issue
    text = text.replace(
        "properlyanymore",
        "properly anymore"
    )

    # Replace slash with space
    text = text.replace("/", " ")

    # Remove unnecessary punctuation
    text = re.sub(
        r"[^\w\s-]",
        "",
        text
    )

    # Remove extra spaces again
    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# SEVERITY ANALYSIS
# ============================================================

HIGH_SEVERITY_PHRASES = {
    "fire",
    "smoke",
    "sparks",
    "electric shock",
    "electrical shock",
    "exploded",
    "explosion",
    "burning",
    "overheating",
    "dangerous",
    "stopped working completely",
    "stopped completely",
    "water is leaking"
}


MEDIUM_SEVERITY_PHRASES = {
    "loud noise",
    "strange noise",
    "strange smell",
    "sometimes stops",
    "vibrates",
    "shakes",
    "leaking",
    "leak",
    "fault",
    "problem",
    "not cooling",
    "not heating",
    "not working",
    "error code",
    "wont reset",
}

def analyze_severity(text):
    """
    Determine complaint severity using predefined rules.

    Returns:
        High
        Medium
        Low
    """

    for phrase in HIGH_SEVERITY_PHRASES:

        if phrase in text:
            return "High"

    for phrase in MEDIUM_SEVERITY_PHRASES:

        if phrase in text:
            return "Medium"

    return "Low"


# ============================================================
# CATEGORY CLASSIFICATION
# ============================================================

CATEGORY_KEYWORDS = {

    "Electrical": {
        "electrical": 4,
        "electric": 4,
        "power": 3,
        "voltage": 3,
        "spark": 4,
        "sparks": 4,
        "shock": 5,
        "wiring": 4,
        "error code": 5,
        "wont reset": 5,
        "longer than usual": 4,
        "takes much longer": 4,
    },

    "Mechanical": {
        "loud noise": 5,
        "strange noise": 5,
        "noise": 3,
        "vibrates": 5,
        "vibration": 5,
        "shakes": 4,
        "bearing": 5,
        "motor": 4,
        "rotation": 4
    },

    "Cooling": {
        "not cooling": 6,
        "does not cool": 6,
        "doesnt cool": 6,
        "cooling": 3,
        "cold": 3,
        "freezing": 4,
        "compressor": 5
    },

    "Heating": {
        "not heating": 6,
        "does not heat": 6,
        "doesnt heat": 6,
        "heating": 3,
        "heater": 3,
        "temperature": 3
    },

    "Leakage": {
        "leak": 6,
        "leaking": 6,
        "dripping": 6,
        "water is leaking": 7
    },

    "Performance": {
        "stopped working": 6,
        "stopped working completely": 7,
        "stopped completely": 6,
        "not working": 6,
        "not functioning": 6,
        "doesnt work": 6,
        "cannot": 4,
        "unable": 4,
        "slow": 3,
        "stops": 3
    },

    "Odor": {
        "strange smell": 7,
        "bad smell": 6,
        "burning smell": 7,
        "smell": 4,
        "odor": 4
    }
}


def analyze_category(text):
    """
    Classify the complaint into a technical category.
    """

    scores = {}

    for category, keywords in CATEGORY_KEYWORDS.items():

        score = 0

        for keyword, weight in keywords.items():

            if keyword in text:
                score += weight

        scores[category] = score

    best_category = max(
        scores,
        key=scores.get
    )

    if scores[best_category] == 0:
        return "Other"

    return best_category


# ============================================================
# SYMPTOM EXTRACTION
# ============================================================

SYMPTOMS = {

    "loud noise": [
        "loud noise",
        "strange noise",
        "noise"
    ],

    "stops during operation": [
        "sometimes stops",
        "stops during operation"
    ],

    "stopped working": [
        "stopped working",
        "stopped completely"
    ],

    "strange smell": [
        "strange smell",
        "bad smell",
        "smell",
        "odor"
    ],

    "vibration": [
        "vibrates",
        "vibration",
        "shakes"
    ],

    "leakage": [
        "leaking",
        "leak",
        "dripping"
    ],

    "not cooling": [
        "not cooling",
        "does not cool",
        "doesnt cool"
    ],

    "not heating": [
        "not heating",
        "not cooling heating",
        "does not heat",
        "doesnt heat"
    ],

    "not working": [
        "not working",
        "not functioning"
    ],

    "error code": [
        "error code",
        "wont reset"
    ],

    "slow cycle": [
        "longer than usual",
        "complete a cycle",
        "takes much longer"
    ]
}


def extract_symptoms(text):
    """
    Extract known symptoms from the complaint.
    """

    found_symptoms = []

    for symptom, keywords in SYMPTOMS.items():

        for keyword in keywords:

            if keyword in text:

                found_symptoms.append(
                    symptom
                )

                break

    return ", ".join(found_symptoms)


# ============================================================
# COMPLETE COMPLAINT ANALYSIS
# ============================================================

def analyze_complaint(complaint_text):
    """
    Perform complete AI/NLP analysis of a customer complaint.

    The analysis includes:

    1. Text preprocessing
    2. VADER sentiment analysis
    3. Severity detection
    4. Category classification
    5. Symptom extraction

    Returns a dictionary containing all results.
    """

    # Step 1: preprocess complaint
    processed_text = preprocess_text(
        complaint_text
    )

    # Step 2: VADER sentiment
    sentiment = analyze_sentiment(
        processed_text
    )

    # Step 3: severity
    severity = analyze_severity(
        processed_text
    )

    # Step 4: category
    category = analyze_category(
        processed_text
    )

    # Step 5: symptoms
    symptoms = extract_symptoms(
        processed_text
    )

    # Return complete analysis
    return {

        "processed_text": processed_text,

        "sentiment": sentiment,

        "severity": severity,

        "symptoms": symptoms,

        "category": category,

        "model_version": MODEL_VERSION
    }