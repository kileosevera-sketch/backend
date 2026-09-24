
from pathlib import Path
from app.db.database import get_connection


def main() :
    migration_file = Path("migrations/sprint2_insights.sql")

    sql = migration_file.read_text(encoding="utf-8")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)

    print("Sprint 2 database migration completed successfully.")


if __name__ == "__main__":
    main()
