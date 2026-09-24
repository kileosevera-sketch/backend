from app.db.database import get_connection


with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'complaint_insights'
            ORDER BY ordinal_position;
        """)

        columns = cur.fetchall()

        print("\nComplaint Insights columns:")
        print("---------------------------")

        for column in columns:
            print(column)
