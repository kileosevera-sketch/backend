"""Run once to create the very first admin account.

Usage: python seed.py
"""
import os

from app.core.security import hash_password
from app.db.database import get_connection


ADMIN_NAME = "System Administrator"
ADMIN_EMAIL = os.getenv("SEED_ADMIN_EMAIL", "admin@company.com")
ADMIN_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD", "ChangeMe123!")


def run():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", (ADMIN_EMAIL,))
            if cur.fetchone():
                print(f"Admin user already exists: {ADMIN_EMAIL}")
                return
            cur.execute(
                """
                INSERT INTO users (full_name, email, password_hash, role, is_first_login, is_active)
                VALUES (%s, %s, %s, 'admin', TRUE, TRUE)
                """,
                (ADMIN_NAME, ADMIN_EMAIL, hash_password(ADMIN_PASSWORD)),
            )
    print("Seeded admin user:")
    print(f"  email:    {ADMIN_EMAIL}")
    print(f"  password: {ADMIN_PASSWORD}")
    print("Change this password after first login.")


if __name__ == "__main__":
    run()
