from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import settings
from app.api.v1.router import api_router
from app.db.session import get_db, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Perform healthcheck ping against database
    print(f"Starting {settings.PROJECT_NAME}...")
    print(f"Connecting to database: {settings.MASKED_DATABASE_URI}")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            print("[OK] Database connection verified on startup!")
    except Exception as e:
        print(f"[WARN] Database connection failed on startup: {e}")
    
    yield
    # Shutdown
    print(f"Shutting down {settings.PROJECT_NAME}...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS Middleware setup
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["Health"])
@app.get(f"{settings.API_V1_STR}/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "service": settings.PROJECT_NAME,
            "database": "connected"
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "error",
                "service": settings.PROJECT_NAME,
                "database": "disconnected",
                "detail": str(e)
            }
        )
