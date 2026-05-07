"""
Modèle ORM SQLAlchemy — table `users`.

Règles :
- UUID côté app (pas serial PostgreSQL) → portable, pas devinable
- Mot de passe : jamais en clair, uniquement le hash bcrypt
- Suppression : logique (is_active=False), jamais physique
- Timestamps : gérés par PostgreSQL via server_default
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class UserRole(str, enum.Enum):
    """Héritage de str → sérialisation JSON directe sans conversion."""
    ADMIN = "admin"
    MANAGER = "manager"
    AGENT = "agent"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), nullable=False, default=UserRole.AGENT
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"