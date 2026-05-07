"""
Script de seed — initialise les données de base en base de données.

Usage :
    cd backend
    source .venv/bin/activate
    python -m scripts.seed

Ce script est idempotent : il peut être relancé sans créer de doublons.
"""

import asyncio
import sys
import os

# Permet d'importer les modules de l'app depuis le dossier backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.db.session import AsyncSessionLocal, engine, Base
from app.models.user import User, UserRole
from app.services.user_service import hash_password


# ── Données initiales ──────────────────────────────────────────────────────────

INITIAL_USERS = [
    {
        "email": "admin@kes-africa.com",
        "full_name": "Administrateur",
        "password": "Admin1234",
        "role": UserRole.ADMIN,
    },
    {
        "email": "manager@kes-africa.com",
        "full_name": "Manager Test",
        "password": "Manager1234",
        "role": UserRole.MANAGER,
    },
    {
        "email": "agent@kes-africa.com",
        "full_name": "Agent Test",
        "password": "Agent1234",
        "role": UserRole.AGENT,
    },
]


async def seed():
    print("Démarrage du seed...\n")

    async with AsyncSessionLocal() as db:
        for user_data in INITIAL_USERS:
            # Vérification : on n'insère pas si l'email existe déjà
            result = await db.execute(
                select(User).where(User.email == user_data["email"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"{user_data['email']} existe déjà — ignoré")
                continue

            user = User(
                email=user_data["email"],
                full_name=user_data["full_name"],
                hashed_password=hash_password(user_data["password"]),
                role=user_data["role"],
                is_active=True,
            )
            db.add(user)
            print(f"  ✅ {user_data['email']} créé ({user_data['role'].value})")

        await db.commit()

    print("\n✅ Seed terminé.")
    print("\nComptes disponibles :")
    for u in INITIAL_USERS:
        print(f"  {u['role'].value:<10} {u['email']:<35} mot de passe : {u['password']}")


if __name__ == "__main__":
    asyncio.run(seed())