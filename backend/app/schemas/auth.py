"""Schémas pour les flux d'authentification."""

from pydantic import BaseModel, EmailStr, field_validator

from app.schemas.user import UserResponse


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Minimum 8 caractères.")
        if not any(c.isupper() for c in v):
            raise ValueError("Au moins une majuscule.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Au moins un chiffre.")
        return v