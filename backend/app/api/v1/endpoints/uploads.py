"""
Endpoint d'upload de fichiers.
Stocke localement dans un premier temps.
Architecture prévue pour S3/MinIO plus tard.
"""

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status

from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

# Dossier de stockage local — à remplacer par S3 en production
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_TYPES = {"application/pdf", "image/png", "image/jpeg"}
MAX_SIZE_MB   = 5
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
):
    """
    Upload un fichier. Retourne l'URL relative.
    Validation : type MIME + taille.
    """
    # Vérification du type
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Type de fichier non autorisé. Formats acceptés : PDF, PNG, JPEG.",
        )

    # Lecture et vérification taille
    content = await file.read()
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Fichier trop volumineux. Maximum : {MAX_SIZE_MB} Mo.",
        )

    # Nom unique pour éviter les collisions
    ext = file.filename.split(".")[-1] if file.filename else "bin"
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(content)

    return {"url": f"/uploads/{filename}", "filename": file.filename}