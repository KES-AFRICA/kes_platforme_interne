"""
Point d'entrée FastAPI.
Configure CORS, gestionnaire d'erreurs global, monte les routeurs.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.core.config import settings
from app.api.v1.router import api_router

from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValidationError)
async def pydantic_validation_handler(request: Request, exc: ValidationError):
    """
    Transforme les erreurs Pydantic en message lisible.
    Sans ça, FastAPI renvoie un objet brut que React ne peut pas afficher.
    """
    errors = exc.errors()
    messages = []
    for err in errors:
        field = " → ".join(str(loc) for loc in err.get("loc", []))
        msg = err.get("msg", "Erreur de validation")
        messages.append(f"{field} : {msg}" if field else msg)
    return JSONResponse(
        status_code=422,
        content={"detail": " | ".join(messages)},
    )


@app.exception_handler(422)
async def unprocessable_handler(request: Request, exc):
    """Attrape les 422 FastAPI natifs et les normalise."""
    body = getattr(exc, "detail", None)
    if isinstance(body, list):
        messages = []
        for err in body:
            if isinstance(err, dict):
                field = " → ".join(str(loc) for loc in err.get("loc", []))
                msg = err.get("msg", "Erreur")
                messages.append(f"{field} : {msg}" if field else msg)
            else:
                messages.append(str(err))
        return JSONResponse(
            status_code=422,
            content={"detail": " | ".join(messages)},
        )
    return JSONResponse(
        status_code=422,
        content={"detail": str(body) if body else "Données invalides."},
    )


app.include_router(api_router, prefix="/api/v1")

uploads_dir = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")


@app.get("/health", tags=["system"])
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}