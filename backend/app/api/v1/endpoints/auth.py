"""
Endpoints d'authentification.

POST /api/v1/auth/login    → connexion
POST /api/v1/auth/refresh  → renouvellement du token
POST /api/v1/auth/logout   → déconnexion
GET  /api/v1/auth/me       → profil utilisateur connecté
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services import user_service

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Message d'erreur volontairement vague : on ne distingue pas
    "email inconnu" de "mauvais mot de passe" pour éviter l'énumération des comptes.
    """
    user = await user_service.get_user_by_email(db, data.email)

    if not user or not user_service.verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce compte est désactivé. Contactez un administrateur.",
        )

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(data.refresh_token)

    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalide ou expiré.",
        )

    user = await user_service.get_user_by_id(db, uuid.UUID(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable ou désactivé.",
        )

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        user=UserResponse.model_validate(user),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: User = Depends(get_current_user)):
    """
    Les JWT sont stateless — pas d'invalidation côté serveur sans Redis.
    Le frontend supprime simplement ses tokens locaux.
    TODO : blacklist Redis si nécessaire.
    """
    return


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user