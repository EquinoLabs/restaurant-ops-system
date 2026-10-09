from app.core.config import normalize_postgres_dsn, Settings


def test_normalize_postgres_dsn_schemes():
    # standard postgresql://
    assert normalize_postgres_dsn("postgresql://user:pass@ep-123.neon.tech/neondb?sslmode=require") == \
           "postgresql+psycopg://user:pass@ep-123.neon.tech/neondb?sslmode=require"

    # legacy postgres://
    assert normalize_postgres_dsn("postgres://user:pass@ep-123.neon.tech/neondb?sslmode=require") == \
           "postgresql+psycopg://user:pass@ep-123.neon.tech/neondb?sslmode=require"

    # already correct postgresql+psycopg://
    assert normalize_postgres_dsn("postgresql+psycopg://user:pass@ep-123.neon.tech/neondb?sslmode=require") == \
           "postgresql+psycopg://user:pass@ep-123.neon.tech/neondb?sslmode=require"


def test_database_url_precedence_and_masking():
    # Case 1: DATABASE_URL provided
    neon_url = "postgresql://neonuser:secretpass123@ep-cool-12345.ap-southeast-1.aws.neon.tech/roms_db?sslmode=require"
    s = Settings(DATABASE_URL=neon_url)

    assert s.SQLALCHEMY_DATABASE_URI == "postgresql+psycopg://neonuser:secretpass123@ep-cool-12345.ap-southeast-1.aws.neon.tech/roms_db?sslmode=require"
    assert "secretpass123" not in s.MASKED_DATABASE_URI
    assert "****" in s.MASKED_DATABASE_URI
    assert "ep-cool-12345.ap-southeast-1.aws.neon.tech" in s.MASKED_DATABASE_URI

    # Case 2: DATABASE_URL not set -> fallback to POSTGRES_* vars
    s_fallback = Settings(DATABASE_URL=None, POSTGRES_USER="localuser", POSTGRES_PASSWORD="localpass", POSTGRES_SERVER="localhost", POSTGRES_PORT=5432, POSTGRES_DB="testdb")
    assert s_fallback.SQLALCHEMY_DATABASE_URI == "postgresql+psycopg://localuser:localpass@localhost:5432/testdb"
    assert "localpass" not in s_fallback.MASKED_DATABASE_URI
    assert "****" in s_fallback.MASKED_DATABASE_URI
