from app.db.database import get_connection
from app.ai.complaint_analyzer import analyze_complaint


def predict_failure(complaint_text):
    """
    Predict failure causes for a new complaint by looking up
    PRE-COMPUTED predictions (from rank_failure_causes.py), instead of
    re-scanning the whole historical database every time.
    """

    analysis = analyze_complaint(complaint_text)
    category = analysis["category"]
    symptoms = analysis["symptoms"]
    severity = analysis["severity"]

    print("\n==============================================")
    print("AI FAILURE PREDICTION")
    print("==============================================")
    print("\nNew complaint:")
    print(complaint_text)
    print("\nAI analysis:")
    print(f"Category: {category}")
    print(f"Symptoms: {symptoms or 'None identified'}")
    print(f"Severity: {severity}")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT predicted_cause, probability, evidence_summary
                FROM predictions
                WHERE symptom = %s
                ORDER BY probability DESC;
            """, (symptoms,))
            rows = cur.fetchall()

    if not rows:
        print(
            "\nNo pre-computed predictions found for this symptom. "
            "Run rank_failure_causes.py first to refresh predictions."
        )
        print("\n==============================================")
        print("PREDICTION COMPLETED")
        print("==============================================")
        return

    print(f"\n----------------------------------------------")
    print(f"PREDICTED FAILURE CAUSES (from predictions table)")
    print(f"----------------------------------------------")

    for rank, r in enumerate(rows, start=1):
        print(f"\n{rank}. {r['predicted_cause']}")
        print(f"   Probability: {r['probability']}%")
        print(f"   Evidence: {r['evidence_summary']}")

    print("\n==============================================")
    print("PREDICTION COMPLETED")
    print("==============================================")


if __name__ == "__main__":
    test_complaint = (
        "My refrigerator makes a loud noise "
        "during operation and sometimes stops."
    )
    predict_failure(test_complaint)