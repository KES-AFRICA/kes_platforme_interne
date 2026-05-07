"""
Dépendances FastAPI — injectées dans les endpoints via Depends().

Usage dans un endpoint :
    async def ma_route(current_user: User = Depends(get_current_user)):
    async def admin_route(current_user: User = Depends(require_admin)):
"""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User, UserRole
from app.services import user_service

# FastAPI lit le token dans le header : "Authorization: Bearer <token>"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Vérifie le JWT et retourne l'utilisateur. Lève 401 si invalide."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalide ou expiré.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        raise credentials_exception

    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exception

    user = await user_service.get_user_by_id(db, uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise credentials_exception

    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Lève 403 si l'utilisateur n'est pas admin."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs.",
        )
    return current_user


async def require_manager_or_above(current_user: User = Depends(get_current_user)) -> User:
    """Lève 403 si l'utilisateur est agent."""
    if current_user.role not in (UserRole.ADMIN, UserRole.MANAGER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux managers et administrateurs.",
        )
    return current_user