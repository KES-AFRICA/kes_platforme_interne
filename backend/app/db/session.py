"""
Connexion PostgreSQL async via SQLAlchemy.

Pourquoi async ? FastAPI est async. Un driver sync bloquerait le serveur
entier pendant chaque requête DB. Avec asyncpg, tout tourne en parallèle.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# Moteur de connexion — pool de 10 connexions permanent + 20 en pic
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,       # affiche le SQL si DEBUG=True
    pool_pre_ping=True,        # vérifie que la connexion est vivante avant usage
    pool_size=10,
    max_overflow=20,
)

# Factory de sessions — une session par requête HTTP
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Classe de base dont héritent tous les modèles ORM."""
    pass


async def get_db() -> AsyncSession:
    """
    Dépendance FastAPI : injectée via Depends(get_db) dans les endpoints.
    Garantit commit auto si succès, rollback si erreur.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise