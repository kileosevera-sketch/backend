from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_current_user, require_role
from app.core.security import hash_password
from app.db.database import get_connection
from app.schemas.auth import ChangePasswordRequest
from app.schemas.user import UserCreate, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, _admin=Depends(require_role("admin"))):
    """Admin-only: create a new user account and assign a role."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", (payload.email,))
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A user with this email already exists",
                )
            cur.execute(
                """
                INSERT INTO users (full_name, email, password_hash, role, is_first_login, is_active)
                VALUES (%s, %s, %s, %s, TRUE, TRUE)
                RETURNING id, full_name, email, role, is_first_login, is_active
                """,
                (
                    payload.full_name,
                    payload.email,
                    hash_password(payload.password),
                    payload.role,
                ),
            )
            row = cur.fetchone()
    return row


@router.get("/me", response_model=UserOut)
def get_me(current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, full_name, email, role, is_first_login, is_active
                FROM users WHERE id = %s
                """,
                (current_user["id"],),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return row


@router.post("/me/change-password")
def change_password(
    payload: ChangePasswordRequest, current_user: dict = Depends(get_current_user)
):
    if len(payload.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters",
        )
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s, is_first_login = FALSE WHERE id = %s",
                (hash_password(payload.new_password), current_user["id"]),
            )
    return {"message": "Password updated successfully"}
