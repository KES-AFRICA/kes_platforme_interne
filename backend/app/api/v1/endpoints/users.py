"""
Endpoints CRUD utilisateurs.

GET    /api/v1/users         → liste paginée  (manager+)
GET    /api/v1/users/stats   → stats dashboard (admin)
POST   /api/v1/users         → créer          (admin)
GET    /api/v1/users/{id}    → détail         (manager+)
PATCH  /api/v1/users/{id}    → modifier       (admin)
DELETE /api/v1/users/{id}    → désactiver     (admin)
"""

import math
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin, require_manager_or_above
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserListResponse, UserResponse, UserUpdate
from app.services import user_service

router = APIRouter()


@router.get("/stats")
async def get_stats(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await user_service.get_users_stats(db)


@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    _: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db),
):
    users, total = await user_service.get_users(
        db, page=page, size=size, role=role, is_active=is_active, search=search
    )
    pages = math.ceil(total / size) if total > 0 else 1
    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total, page=page, size=size, pages=pages,
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await user_service.create_user(db, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    _: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable.")
    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable.")

    if user_id == current_user.id and data.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas désactiver votre propre compte.",
        )

    user = await user_service.update_user(db, user, data)
    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas désactiver votre propre compte.",
        )

    user = await user_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable.")

    await user_service.deactivate_user(db, user)