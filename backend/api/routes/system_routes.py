from fastapi import APIRouter, Response

from backend.services.runtime_readiness_service import RuntimeReadinessService


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
def readiness(response: Response):
    result = RuntimeReadinessService().status()
    if not result["success"]:
        response.status_code = 503
    return result
