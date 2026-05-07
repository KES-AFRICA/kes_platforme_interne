"""
Modèles ORM pour le module Congés & Permissions.

Architecture du workflow :
- Agent crée → status PENDING_MANAGER
- Manager approuve → status PENDING_ADMIN
- Admin approuve → status APPROVED
- Refus à n'importe quelle étape → status REJECTED

Les permissions (horaires) suivent le même workflow.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey,
    Integer, String, Text, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


# ── Enums ──────────────────────────────────────────────────────────────────────

class LeaveType(str, enum.Enum):
    CA   = "CA"    # Congé annuel
    CM   = "CM"    # Congé maladie
    CSS  = "CSS"   # Congé sans solde
    CMAT = "CMAT"  # Congé maternité
    CPAT = "CPAT"  # Congé paternité
    CEXC = "CEXC"  # Congé exceptionnel
    CFOR = "CFOR"  # Congé formation
    CPAR = "CPAR"  # Congé parental


class PermissionType(str, enum.Enum):
    FULL_DAY  = "FULL_DAY"   # Permission journalière
    HALF_DAY  = "HALF_DAY"   # Demi-journée
    HOURLY    = "HOURLY"     # Permission horaire


class RequestStatus(str, enum.Enum):
    PENDING_MANAGER = "PENDING_MANAGER"  # En attente validation manager
    PENDING_ADMIN   = "PENDING_ADMIN"    # Validé manager, en attente admin
    APPROVED        = "APPROVED"         # Approuvé définitivement
    REJECTED        = "REJECTED"         # Refusé


class RequestCategory(str, enum.Enum):
    LEAVE      = "LEAVE"       # Congé
    PERMISSION = "PERMISSION"  # Permission


# ── Modèle principal ───────────────────────────────────────────────────────────

class LeaveRequest(Base):
    """
    Table unifiée pour congés et permissions.
    category distingue les deux types.
    Les champs horaires (time_start, time_end) ne s'appliquent qu'aux permissions.
    """

    __tablename__ = "leave_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Demandeur ──────────────────────────────────────────────────────────────
    requester_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requester = relationship("User", foreign_keys=[requester_id])

    # ── Catégorie et type ──────────────────────────────────────────────────────
    category: Mapped[RequestCategory] = mapped_column(
        Enum(RequestCategory, name="request_category"),
        nullable=False,
        index=True,
    )
    leave_type: Mapped[LeaveType | None] = mapped_column(
        Enum(LeaveType, name="leave_type"),
        nullable=True,
    )
    permission_type: Mapped[PermissionType | None] = mapped_column(
        Enum(PermissionType, name="permission_type"),
        nullable=True,
    )

    # ── Dates & heures ─────────────────────────────────────────────────────────
    date_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    date_end:   Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    time_start: Mapped[str | None] = mapped_column(String(5), nullable=True)  # "08:00"
    time_end:   Mapped[str | None] = mapped_column(String(5), nullable=True)  # "12:00"

    # Calculé automatiquement côté backend (jours ouvrables)
    working_days: Mapped[float] = mapped_column(nullable=False, default=0)

    # ── Contenu ────────────────────────────────────────────────────────────────
    description:   Mapped[str]       = mapped_column(Text, nullable=False)
    attachment_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ── Workflow ───────────────────────────────────────────────────────────────
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, name="request_status"),
        nullable=False,
        default=RequestStatus.PENDING_MANAGER,
        index=True,
    )

    # Validation Manager
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    manager          = relationship("User", foreign_keys=[manager_id])
    manager_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    manager_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Validation Admin
    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    admin            = relationship("User", foreign_keys=[admin_id])
    admin_comment:   Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Timestamps ─────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<LeaveRequest id={self.id} status={self.status} category={self.category}>"