from fastapi import APIRouter
from backend.app.schemas.common import APIResponse

api_v1_router = APIRouter(prefix="/v1")


@api_v1_router.get("/health", response_model=APIResponse[dict])
async def health_check():
    """System health and readiness verification."""
    return APIResponse(
        success=True,
        message="SentinelAI Platform Engine Operational",
        data={
            "status": "HEALTHY",
            "version": "0.1.0",
            "subsystems": {
                "database": "CONNECTED",
                "security_firewall": "ACTIVE",
                "mock_provider": "READY",
                "rag_engine": "STANDBY",
            }
        }
    )
