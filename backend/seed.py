"""Run once to create the very first admin account.

Usage: python seed.py
"""
import os

from app.core.security import hash_password
from app.db.database import get_connection


ADMIN_NAME = "System Administrator"
ADMIN_EMAIL = os.getenv("SEED_ADMIN_EMAIL", "admin@company.com")
ADMIN_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD", "ChangeMe123!")
DEMO_USERS = [
    ("QA User", "qa@company.com", "qa123", "qa"),
    ("Engineering User", "engineer@company.com", "engineer123", "engineering"),
    ("Customer Support User", "cs@company.com", "cs123", "customer_service"),
]


def run():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", (ADMIN_EMAIL,))
            if not cur.fetchone():
                cur.execute(
                    """
                    INSERT INTO users (full_name, email, password_hash, role, is_first_login, is_active)
                    VALUES (%s, %s, %s, 'admin', TRUE, TRUE)
                    """,
                    (ADMIN_NAME, ADMIN_EMAIL, hash_password(ADMIN_PASSWORD)),
                )
                print(f"Seeded admin user: {ADMIN_EMAIL}")

            for full_name, email, password, role in DEMO_USERS:
                cur.execute("SELECT id FROM users WHERE email = %s", (email,))
                user = cur.fetchone()
                if user:
                    cur.execute(
                        """
                        UPDATE users
                        SET password_hash = %s, role = %s, is_active = TRUE, is_first_login = FALSE
                        WHERE id = %s
                        """,
                        (hash_password(password), role, user["id"]),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO users (full_name, email, password_hash, role, is_first_login, is_active)
                        VALUES (%s, %s, %s, %s, FALSE, TRUE)
                        """,
                        (full_name, email, hash_password(password), role),
                    )
                    print(f"Seeded demo user: {email} / {password}")


if __name__ == "__main__":
    run()
