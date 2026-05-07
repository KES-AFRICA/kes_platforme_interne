"""
Configuration globale de l'application.
Charge les variables depuis .env via pydantic-settings.
Pydantic lève une erreur au démarrage si une variable obligatoire manque.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Plateforme Interne"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # PostgreSQL
    DATABASE_URL: str                    # obligatoire — doit être dans .env

    # JWT
    SECRET_KEY: str                      # obligatoire — généré avec secrets.token_hex(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS — origines autorisées à appeler l'API
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"
        case_sensitive = True


# Instance unique importée partout dans l'app
settings = Settings()