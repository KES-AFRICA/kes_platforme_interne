"""
Service utilisateur — toute la logique métier.

Règle : les endpoints ne touchent jamais la DB directement.
Ils appellent les services, qui appellent la DB.

Couches :
  endpoint → service → DB
"""

import math
import uuid
from typing import Optional

from passlib.context import CryptContext
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate

# bcrypt est le standard pour les mots de passe
# deprecated="auto" met à jour les vieux hashes automatiquement
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Utilitaires mot de passe ───────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Lecture ────────────────────────────────────────────────────────────────────

async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Recherche insensible à la casse."""
    result = await db.execute(
        select(User).where(func.lower(User.email) == email.lower())
    )
    return result.scalar_one_or_none()


async def get_users(
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
) -> tuple[list[User], int]:
    """Liste paginée avec filtres. Retourne (utilisateurs, total)."""
    query = select(User)
    count_query = select(func.count()).select_from(User)

    if role is not None:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)

    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)

    if search:
        pattern = f"%{search}%"
        condition = User.full_name.ilike(pattern) | User.email.ilike(pattern)
        query = query.where(condition)
        count_query = count_query.where(condition)

    total = (await db.execute(count_query)).scalar_one()

    offset = (page - 1) * size
    query = query.order_by(User.created_at.desc()).offset(offset).limit(size)
    users = (await db.execute(query)).scalars().all()

    return users, total


# ── Écriture ───────────────────────────────────────────────────────────────────

async def create_user(db: AsyncSession, data: UserCreate) -> User:
    """
    Crée un utilisateur.
    Raises ValueError si l'email existe déjà.
    """
    if await get_user_by_email(db, data.email):
        raise ValueError(f"L'email {data.email} est déjà utilisé.")

    user = User(
        email=data.email.lower(),
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def update_user(db: AsyncSession, user: User, data: UserUpdate) -> User:
    """Met à jour uniquement les champs fournis (non None)."""
    update_data = data.model_dump(exclude_none=True)

    if "password" in update_data:
        update_data["hashed_password"] = hash_password(update_data.pop("password"))

    for field, value in update_data.items():
        setattr(user, field, value)

    await db.flush()
    await db.refresh(user)
    return user


async def deactivate_user(db: AsyncSession, user: User) -> User:
    """Soft delete — l'enregistrement reste en base."""
    user.is_active = False
    await db.flush()
    await db.refresh(user)
    return user


# ── Stats dashboard ────────────────────────────────────────────────────────────

async def get_users_stats(db: AsyncSession) -> dict:
    total = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    active = (await db.execute(
        select(func.count()).select_from(User).where(User.is_active == True)
    )).scalar_one()

    by_role = {}
    for role in UserRole:
        count = (await db.execute(
            select(func.count()).select_from(User).where(User.role == role)
        )).scalar_one()
        by_role[role.value] = count

    return {"total": total, "active": active, "inactive": total - active, "by_role": by_role}