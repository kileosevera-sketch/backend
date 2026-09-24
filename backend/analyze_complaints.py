from app.db.database import get_connection
from app.ai.complaint_analyzer import analyze_complaint


def analyze_all_complaints():
    """
    Read all complaints from PostgreSQL,
    analyze them using the AI/NLP analyzer,
    and save the results into complaint_insights.
    """

    with get_connection() as conn:

        with conn.cursor() as cur:

            # -------------------------------------------------
            # 1. Get all complaints that need analysis
            # -------------------------------------------------

            cur.execute("""
                SELECT c.id, c.description
                FROM complaints c
                LEFT JOIN complaint_insights ci ON ci.complaint_id = c.id
                WHERE ci.id IS NULL
                ORDER BY c.id;
            """)

            complaints = cur.fetchall()

            print(f"Found {len(complaints)} complaints to analyze.")

            # -------------------------------------------------
            # 2. Analyze each complaint
            # -------------------------------------------------

            analyzed_count = 0

            for complaint in complaints:

                complaint_id = complaint["id"]
                description = complaint["description"]

                # Run our AI/NLP analyzer
                result = analyze_complaint(description)

                # -------------------------------------------------
                # 3. Save the AI/NLP result
                # -------------------------------------------------

                cur.execute("""
                    INSERT INTO complaint_insights (
                        complaint_id,
                        sentiment,
                        severity,
                        symptoms,
                        category,
                        processed_text,
                        model_version,
                        confidence
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s
                    );
                """, (
                    complaint_id,
                    result["sentiment"],
                    result["severity"],
                    result["symptoms"],
                    result["category"],
                    result["processed_text"],
                    result["model_version"],
                    None
                ))

                analyzed_count += 1

                print(
                    f"Complaint {complaint_id} analyzed: "
                    f"{result['category']} | "
                    f"{result['severity']} | "
                    f"{result['sentiment']}"
                )

            # -------------------------------------------------
            # 4. Commit all changes
            # -------------------------------------------------

            conn.commit()

            print("\n======================================")
            print("AI/NLP ANALYSIS COMPLETED")
            print("======================================")
            print(f"Complaints analyzed: {analyzed_count}")


if __name__ == "__main__":
    analyze_all_complaints()
