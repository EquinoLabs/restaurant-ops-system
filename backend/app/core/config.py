import json
from typing import List, Union, Optional
from urllib.parse import urlparse, urlunparse
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_postgres_dsn(dsn: str) -> str:
    """
    Safely normalizes PostgreSQL DSN schemes to use SQLAlchemy 2.x psycopg driver scheme ('postgresql+psycopg://').
    Preserves all query parameters (such as sslmode=require), path, host, port, credentials intact.
    """
    if not dsn:
        return dsn

    parsed = urlparse(dsn)
    scheme = parsed.scheme.lower()

    if scheme in ("postgres", "postgresql"):
        new_scheme = "postgresql+psycopg"
        # Reconstruct URL with updated scheme
        return urlunparse((new_scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    
    return dsn


class Settings(BaseSettings):
    PROJECT_NAME: str = "Restaurant Operations Management System"
    API_V1_STR: str = "/api/v1"

    # Preferred direct database connection string (e.g. Neon PostgreSQL)
    DATABASE_URL: Optional[str] = None

    # Fallback individual PostgreSQL settings for local development / Docker
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "roms_user"
    POSTGRES_PASSWORD: str = "roms_password"
    POSTGRES_DB: str = "roms_db"

    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5176",
        "http://127.0.0.1:5176",
    ]

    JWT_SECRET_KEY: str = "dev_secret_key_change_in_production_1234567890"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # Cloudflare R2 Configuration
    R2_ACCOUNT_ID: Optional[str] = None
    R2_ACCESS_KEY_ID: Optional[str] = None
    R2_SECRET_ACCESS_KEY: Optional[str] = None
    R2_BUCKET_NAME: str = "roms-public-images"
    R2_PUBLIC_BASE_URL: str = "https://pub-roms-dev.r2.dev"
    R2_MAX_IMAGE_BYTES: int = 5 * 1024 * 1024  # 5 MiB limit

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, str) and v.startswith("["):
            return json.loads(v)
        return v

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """
        Determines the authoritative database connection URI.
        Precedence:
        1. If DATABASE_URL is set, normalize its scheme to postgresql+psycopg:// and use it.
        2. Otherwise, construct from individual POSTGRES_* fallback variables.
        """
        if self.DATABASE_URL and self.DATABASE_URL.strip():
            return normalize_postgres_dsn(self.DATABASE_URL.strip())

        raw_uri = (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
        return raw_uri

    @property
    def MASKED_DATABASE_URI(self) -> str:
        """
        Returns a redacted version of the database URI suitable for logs and diagnostic tools.
        Masks the password while revealing host, database name, and driver scheme.
        """
        uri = self.SQLALCHEMY_DATABASE_URI
        try:
            parsed = urlparse(uri)
            if parsed.password:
                masked_netloc = parsed.netloc.replace(f":{parsed.password}@", ":****@")
                return urlunparse((parsed.scheme, masked_netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
            return uri
        except Exception:
            return "postgresql+psycopg://****@hidden/hidden"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()


def get_public_image_url(key_or_url: Optional[str]) -> Optional[str]:
    """
    Derives full public image URL from stored object key or returns legacy URL as-is.
    """
    if not key_or_url:
        return None
    key_or_url = key_or_url.strip()
    if not key_or_url:
        return None
    if key_or_url.startswith("http://") or key_or_url.startswith("https://"):
        return key_or_url
    base = (settings.R2_PUBLIC_BASE_URL or "").rstrip("/")
    if not base:
        return key_or_url
    return f"{base}/{key_or_url.lstrip('/')}"

