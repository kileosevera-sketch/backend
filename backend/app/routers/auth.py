from fastapi import APIRouter, HTTPException, status

from app.core.security import create_access_token, verify_password
from app.db.database import get_connection
from app.schemas.auth import LoginRequest, Token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(payload: LoginRequest):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, password_hash, role, is_active, is_first_login
                FROM users WHERE email = %s
                """,
                (payload.email,),
            )
            user = cur.fetchone()

    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
    )

    if not user or not user["is_active"]:
        raise invalid_credentials
    if not verify_password(payload.password, user["password_hash"]):
        raise invalid_credentials

    token = create_access_token({"sub": str(user["id"]), "role": user["role"]})
    return Token(
        access_token=token,
        role=user["role"],
        must_change_password=user["is_first_login"],
    )
