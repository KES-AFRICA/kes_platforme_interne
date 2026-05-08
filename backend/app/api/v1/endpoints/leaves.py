"""
Endpoints du module Congés & Permissions.

GET    /api/v1/leaves/stats          → stats selon rôle
GET    /api/v1/leaves/my             → mes demandes
GET    /api/v1/leaves/to-review      → demandes à traiter (manager/admin)
GET    /api/v1/leaves/all            → toutes les demandes (admin)
POST   /api/v1/leaves                → créer une demande
GET    /api/v1/leaves/{id}           → détail
PATCH  /api/v1/leaves/{id}/review    → traiter (manager/admin)
"""

import math
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin, require_manager_or_above
from app.db.session import get_db
from app.models.leave import RequestCategory, RequestStatus
from app.models.user import User, UserRole
from app.schemas.leave import (
    LeaveRequestCreate, LeaveRequestListResponse,
    LeaveRequestResponse, LeaveRequestReview, LeaveStatsResponse,
)
from app.services import leave_service

router = APIRouter()


@router.get("/stats")
async def get_stats(
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to:   Optional[str] = Query(None, description="YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timezone

    df = None
    dt = None
    if date_from:
        df = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if date_to:
        dt = datetime.strptime(date_to, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59, tzinfo=timezone.utc
        )

    return await leave_service.get_stats(db, current_user, df, dt)

@router.get("/my", response_model=LeaveRequestListResponse)
async def get_my_requests(
    page:     int = Query(1, ge=1),
    size:     int = Query(20, ge=1, le=100),
    category: Optional[RequestCategory] = None,
    status_filter: Optional[RequestStatus] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Uniquement pour agents et managers."""
    if current_user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Les administrateurs n'ont pas de demandes personnelles.",
        )

    items, total = await leave_service.get_my_requests(
        db, current_user, page, size, category, status_filter
    )
    pages = math.ceil(total / size) if total > 0 else 1
    return LeaveRequestListResponse(
        items=[LeaveRequestResponse.model_validate(i) for i in items],
        total=total, page=page, size=size, pages=pages,
    )


@router.get("/to-review", response_model=LeaveRequestListResponse)
async def get_requests_to_review(
    page:     int = Query(1, ge=1),
    size:     int = Query(20, ge=1, le=100),
    category: Optional[RequestCategory] = None,
    current_user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db),
):
    items, total = await leave_service.get_requests_to_review(
        db, current_user, page, size, category
    )
    pages = math.ceil(total / size) if total > 0 else 1
    return LeaveRequestListResponse(
        items=[LeaveRequestResponse.model_validate(i) for i in items],
        total=total, page=page, size=size, pages=pages,
    )


@router.get("/all", response_model=LeaveRequestListResponse)
async def get_all_requests(
    page:     int = Query(1, ge=1),
    size:     int = Query(20, ge=1, le=100),
    category: Optional[RequestCategory] = None,
    status_filter: Optional[RequestStatus] = Query(None, alias="status"),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    items, total = await leave_service.get_all_requests(
        db, page, size, category, status_filter
    )
    pages = math.ceil(total / size) if total > 0 else 1
    return LeaveRequestListResponse(
        items=[LeaveRequestResponse.model_validate(i) for i in items],
        total=total, page=page, size=size, pages=pages,
    )


@router.post("", response_model=LeaveRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_request(
    data: LeaveRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await leave_service.create_request(db, data, current_user)


@router.get("/{request_id}", response_model=LeaveRequestResponse)
async def get_request(
    request_id:   uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    req = await leave_service.get_request_by_id(db, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Demande introuvable.")

    # Agent ne peut voir que ses propres demandes
    if (current_user.role == UserRole.AGENT
            and req.requester_id != current_user.id):
        raise HTTPException(status_code=403, detail="Accès refusé.")

    return LeaveRequestResponse.model_validate(req)


@router.patch("/{request_id}/review", response_model=LeaveRequestResponse)
async def review_request(
    request_id:   uuid.UUID,
    data:         LeaveRequestReview,
    current_user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db),
):
    req = await leave_service.get_request_by_id(db, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Demande introuvable.")

    return await leave_service.review_request(db, req, current_user, data)