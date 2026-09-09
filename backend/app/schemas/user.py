from typing import Literal

from pydantic import BaseModel, EmailStr

Role = Literal["admin", "management", "engineering", "qa", "customer_service"]


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: Role


class UserOut(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: str
    is_first_login: bool
    is_active: bool
