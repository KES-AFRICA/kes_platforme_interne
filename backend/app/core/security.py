"""
Gestion des tokens JWT.
- create_access_token  → courte durée (30 min), accès aux routes protégées
- create_refresh_token → longue durée (7 jours), renouvellement silencieux
- decode_token         → vérifie signature + expiration
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.core.config import settings


def create_access_token(subject: str) -> str:
    """subject = UUID de l'utilisateur en string."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": subject, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {"sub": subject, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Retourne le payload si valide, None si expiré ou invalide."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None