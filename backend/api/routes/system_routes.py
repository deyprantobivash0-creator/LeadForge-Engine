from fastapi import APIRouter
from sqlalchemy import text

from backend.database.session import SessionLocal


router = APIRouter(
    tags=["system"]
)


@router.get("/health")
def health():
    return {
        "success": True,
        "status": "healthy",
    }


@router.get("/ready")
def readiness():
    db = SessionLocal()

    try:
        db.execute(text("SELECT 1"))

        return {
            "success": True,
            "status": "ready",
            "database": "ok",
        }

    except Exception:
        return {
            "success": False,
            "status": "not_ready",
            "database": "unavailable",
        }

    finally:
        db.close()