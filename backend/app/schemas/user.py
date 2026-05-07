"""
Schémas Pydantic — ce qu'on reçoit et ce qu'on renvoie via l'API.

Séparation stricte :
- UserCreate  → données entrantes (inclut le mot de passe en clair)
- UserUpdate  → modification partielle (tout optionnel)
- UserResponse → données sortantes (jamais le mot de passe)
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import UserRole


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    role: UserRole = UserRole.AGENT


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Le mot de passe doit contenir au moins une majuscule.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Le mot de passe doit contenir au moins un chiffre.")
        return v


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8, max_length=128)


class UserResponse(UserBase):
    id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}   # conversion directe depuis SQLAlchemy


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    size: int
    pages: int