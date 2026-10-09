import sys
from sqlalchemy import text
from app.core.config import settings
from app.db.session import engine


def check_db_connection() -> bool:
    print(f"Connecting to database: {settings.MASKED_DATABASE_URI}")
    try:
        with engine.connect() as conn:
            # Perform basic database ping
            result = conn.execute(text("SELECT 1")).scalar()
            if result == 1:
                # Retrieve server version info safely
                version_str = conn.execute(text("SELECT version()")).scalar()
                print("[OK] Database connection successful!")
                if version_str:
                    first_line = version_str.split("\n")[0]
                    print(f"     Server version: {first_line}")
                return True
            else:
                print("[FAIL] Unexpected response from database ping query.")
                return False
    except Exception as e:
        print("[FAIL] Database connection failed.")
        # Redact any accidental credential leak in exception message
        error_msg = str(e)
        if settings.POSTGRES_PASSWORD and settings.POSTGRES_PASSWORD in error_msg:
            error_msg = error_msg.replace(settings.POSTGRES_PASSWORD, "****")
        print(f"       Error details: {error_msg}")
        return False


if __name__ == "__main__":
    success = check_db_connection()
    sys.exit(0 if success else 1)
