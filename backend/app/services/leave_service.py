"""
Service Congés & Permissions — toute la logique métier.
"""

import math
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.leave import LeaveRequest, RequestCategory, RequestStatus
from app.models.user import User, UserRole
from app.schemas.leave import LeaveRequestCreate, LeaveRequestReview
from app.utils.leave_utils import (
    calculate_permission_hours,
    calculate_working_days,
    validate_minimum_notice,
    validate_time_range,
)


# ── Création ───────────────────────────────────────────────────────────────────

async def create_request(
    db:           AsyncSession,
    data:         LeaveRequestCreate,
    requester:    User,
    attachment_url: Optional[str] = None,
) -> LeaveRequest:
    """
    Crée une demande de congé ou permission.
    Applique toutes les validations métier critiques.
    """

    # Admin ne peut pas créer de demande
    if requester.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Les administrateurs ne peuvent pas créer de demandes.",
        )

    # Délai minimum 48h
    if not validate_minimum_notice(data.date_start):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La demande doit être soumise au minimum 48h avant le début.",
        )

    # Validation horaires pour les permissions
    if data.time_start and data.time_end:
        if not validate_time_range(data.time_start, data.time_end):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Les heures doivent être entre 08:00 et 17:00, et cohérentes.",
            )

    # Calcul jours ouvrables
    working_days = calculate_working_days(
        data.date_start.date(),
        data.date_end.date(),
    )

    # Détermination du statut initial selon le rôle
    # Manager → directement PENDING_ADMIN (pas de validation manager sur soi-même)
    initial_status = (
        RequestStatus.PENDING_ADMIN
        if requester.role == UserRole.MANAGER
        else RequestStatus.PENDING_MANAGER
    )

    request = LeaveRequest(
        requester_id    = requester.id,
        category        = data.category,
        leave_type      = data.leave_type,
        permission_type = data.permission_type,
        date_start      = data.date_start,
        date_end        = data.date_end,
        time_start      = data.time_start,
        time_end        = data.time_end,
        working_days    = working_days,
        description     = data.description,
        attachment_url  = attachment_url,
        status          = initial_status,
    )

    db.add(request)
    await db.flush()
    await db.refresh(request, attribute_names=["requester"])
    return request


# ── Traitement ─────────────────────────────────────────────────────────────────

async def review_request(
    db:       AsyncSession,
    request:  LeaveRequest,
    reviewer: User,
    data:     LeaveRequestReview,
) -> LeaveRequest:
    """
    Traite une demande (approbation ou refus).
    Vérifie que le reviewer a le droit de traiter cette demande.
    """

    # Interdiction de traiter sa propre demande
    if request.requester_id == reviewer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous ne pouvez pas traiter votre propre demande.",
        )

    now = datetime.now(timezone.utc)

    if reviewer.role == UserRole.MANAGER:
        # Manager ne peut traiter que les demandes PENDING_MANAGER
        if request.status != RequestStatus.PENDING_MANAGER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cette demande n'est pas en attente de validation manager.",
            )
        request.manager_id          = reviewer.id
        request.manager_comment     = data.comment
        request.manager_reviewed_at = now
        request.status = (
            RequestStatus.PENDING_ADMIN if data.approved
            else RequestStatus.REJECTED
        )

    elif reviewer.role == UserRole.ADMIN:
        # Admin ne peut traiter que les demandes PENDING_ADMIN
        if request.status != RequestStatus.PENDING_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cette demande n'est pas en attente de validation admin.",
            )
        request.admin_id          = reviewer.id
        request.admin_comment     = data.comment
        request.admin_reviewed_at = now
        request.status = (
            RequestStatus.APPROVED if data.approved
            else RequestStatus.REJECTED
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas les droits pour traiter cette demande.",
        )

    await db.flush()
    await db.refresh(request)
    return request


# ── Lecture ────────────────────────────────────────────────────────────────────

def _base_query_with_relations():
    """Query de base avec les relations chargées en eager loading."""
    return (
        select(LeaveRequest)
        .options(
            selectinload(LeaveRequest.requester),
            selectinload(LeaveRequest.manager),
            selectinload(LeaveRequest.admin),
        )
    )


async def get_request_by_id(
    db:         AsyncSession,
    request_id: uuid.UUID,
) -> Optional[LeaveRequest]:
    result = await db.execute(
        _base_query_with_relations()
        .where(LeaveRequest.id == request_id)
    )
    return result.scalar_one_or_none()


async def get_my_requests(
    db:       AsyncSession,
    user:     User,
    page:     int = 1,
    size:     int = 20,
    category: Optional[RequestCategory] = None,
    status_filter: Optional[RequestStatus] = None,
) -> tuple[list[LeaveRequest], int]:
    """Demandes de l'utilisateur connecté."""
    query = _base_query_with_relations().where(
        LeaveRequest.requester_id == user.id
    )
    count_q = select(func.count()).select_from(LeaveRequest).where(
        LeaveRequest.requester_id == user.id
    )

    if category:
        query   = query.where(LeaveRequest.category == category)
        count_q = count_q.where(LeaveRequest.category == category)
    if status_filter:
        query   = query.where(LeaveRequest.status == status_filter)
        count_q = count_q.where(LeaveRequest.status == status_filter)

    total = (await db.execute(count_q)).scalar_one()
    items = (
        await db.execute(
            query.order_by(LeaveRequest.created_at.desc())
            .offset((page - 1) * size).limit(size)
        )
    ).scalars().all()

    return items, total


async def get_requests_to_review(
    db:       AsyncSession,
    reviewer: User,
    page:     int = 1,
    size:     int = 20,
    category: Optional[RequestCategory] = None,
    status_filter: Optional[RequestStatus] = None,
) -> tuple[list[LeaveRequest], int]:
    """
    Demandes à traiter selon le rôle du reviewer.
    Manager → PENDING_MANAGER (sauf les siennes)
    Admin   → PENDING_ADMIN
    """
    if reviewer.role == UserRole.MANAGER:
        status_condition = LeaveRequest.status == RequestStatus.PENDING_MANAGER
        exclude_own      = LeaveRequest.requester_id != reviewer.id
    elif reviewer.role == UserRole.ADMIN:
        status_condition = LeaveRequest.status == RequestStatus.PENDING_ADMIN
        exclude_own      = True   # Admin n'a pas de demandes
    else:
        return [], 0

    conditions = [status_condition]
    if exclude_own is not True:
        conditions.append(exclude_own)
    elif reviewer.role == UserRole.MANAGER:
        conditions.append(LeaveRequest.requester_id != reviewer.id)

    query = _base_query_with_relations()
    for c in conditions:
        query = query.where(c)

    count_q = select(func.count()).select_from(LeaveRequest)
    for c in conditions:
        count_q = count_q.where(c)

    if category:
        query   = query.where(LeaveRequest.category == category)
        count_q = count_q.where(LeaveRequest.category == category)
    if status_filter:
        query   = query.where(LeaveRequest.status == status_filter)
        count_q = count_q.where(LeaveRequest.status == status_filter)

    total = (await db.execute(count_q)).scalar_one()
    items = (
        await db.execute(
            query.order_by(LeaveRequest.created_at.asc())
            .offset((page - 1) * size).limit(size)
        )
    ).scalars().all()

    return items, total


async def get_all_requests(
    db:       AsyncSession,
    page:     int = 1,
    size:     int = 20,
    category: Optional[RequestCategory] = None,
    status_filter: Optional[RequestStatus] = None,
    search:   Optional[str] = None,
) -> tuple[list[LeaveRequest], int]:
    """Toutes les demandes — admin uniquement."""
    query   = _base_query_with_relations()
    count_q = select(func.count()).select_from(LeaveRequest)

    if category:
        query   = query.where(LeaveRequest.category == category)
        count_q = count_q.where(LeaveRequest.category == category)
    if status_filter:
        query   = query.where(LeaveRequest.status == status_filter)
        count_q = count_q.where(LeaveRequest.status == status_filter)

    total = (await db.execute(count_q)).scalar_one()
    items = (
        await db.execute(
            query.order_by(LeaveRequest.created_at.desc())
            .offset((page - 1) * size).limit(size)
        )
    ).scalars().all()

    return items, total


async def get_stats(
    db:   AsyncSession,
    user: User,
) -> dict:
    """Stats agrégées selon le rôle."""

    async def count(filters: list) -> int:
        q = select(func.count()).select_from(LeaveRequest)
        for f in filters:
            q = q.where(f)
        return (await db.execute(q)).scalar_one()

    base = []
    if user.role == UserRole.AGENT:
        base = [LeaveRequest.requester_id == user.id]

    return {
        "total":           await count(base),
        "approved":        await count([*base, LeaveRequest.status == RequestStatus.APPROVED]),
        "rejected":        await count([*base, LeaveRequest.status == RequestStatus.REJECTED]),
        "pending_manager": await count([*base, LeaveRequest.status == RequestStatus.PENDING_MANAGER]),
        "pending_admin":   await count([*base, LeaveRequest.status == RequestStatus.PENDING_ADMIN]),
        "leaves":          await count([*base, LeaveRequest.category == RequestCategory.LEAVE]),
        "permissions":     await count([*base, LeaveRequest.category == RequestCategory.PERMISSION]),
    }