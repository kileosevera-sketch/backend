"""
Backfill failure_causes table from failures + complaint_insights.
This table was never populated by rank_failure_causes.py — we fix that now.
"""
from app.db.database import get_connection


def backfill():
    with get_connection() as conn:
        with conn.cursor() as cur:

            # Join failures with complaint_insights to get symptom -> cause pairs
            cur.execute("""
                SELECT
                    ci.symptoms AS symptom,
                    f.description AS cause_name,
                    COUNT(*) AS occurrences
                FROM failures f
                JOIN complaint_insights ci ON ci.complaint_id = f.complaint_id
                WHERE f.complaint_id IS NOT NULL
                  AND ci.symptoms IS NOT NULL
                  AND trim(ci.symptoms) <> ''
                GROUP BY ci.symptoms, f.description
                ORDER BY ci.symptoms, occurrences DESC;
            """)
            rows = cur.fetchall()

            if not rows:
                print("No symptom-failure pairs found in the database.")
                return

            # Group by symptom to compute probability
            symptom_groups = {}
            for row in rows:
                symptom_groups.setdefault(row["symptom"], []).append(row)

            # Clear old data — this table is a materialized snapshot
            cur.execute("DELETE FROM failure_causes;")

            total_inserted = 0
            for symptom, causes in symptom_groups.items():
                total = sum(c["occurrences"] for c in causes)
                for c in causes:
                    probability = round((c["occurrences"] / total) * 100, 2)
                    confidence = round(min(100.0, (c["occurrences"] / total) * 100), 2)

                    # Insert one row per failure_causes entry — but we need a failure_id.
                    # The schema has failure_id NOT NULL REFERENCES failures(id).
                    # We insert one representative failure per (symptom, cause) pair.
                    cur.execute("""
                        SELECT f.id
                        FROM failures f
                        JOIN complaint_insights ci ON ci.complaint_id = f.complaint_id
                        WHERE ci.symptoms = %s AND f.description = %s
                        LIMIT 1;
                    """, (symptom, c["cause_name"]))
                    fid_row = cur.fetchone()
                    if not fid_row:
                        continue

                    cur.execute("""
                        INSERT INTO failure_causes
                            (failure_id, cause_name, probability, confidence)
                        VALUES (%s, %s, %s, %s);
                    """, (
                        fid_row["id"],
                        c["cause_name"],
                        probability,
                        confidence,
                    ))
                    total_inserted += 1

            conn.commit()

            print(f"\nBackfill complete.")
            print(f"Symptom patterns: {len(symptom_groups)}")
            print(f"Rows inserted into failure_causes: {total_inserted}")


if __name__ == "__main__":
    backfill()