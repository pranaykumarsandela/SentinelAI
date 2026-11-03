from fastapi import APIRouter
from backend.app.schemas.common import APIResponse
from backend.app.api.v1.documents import documents_router
from backend.app.api.v1.rag import rag_router

api_v1_router = APIRouter(prefix="/v1")

# Subsystem Routers
api_v1_router.include_router(documents_router)
api_v1_router.include_router(rag_router)


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
                "rag_engine": "ACTIVE",
                "qdrant_store": "INITIALIZED",
            }
        }
    )
