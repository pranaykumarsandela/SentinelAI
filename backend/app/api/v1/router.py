from fastapi import APIRouter
from backend.app.schemas.common import APIResponse
from backend.app.api.v1.documents import documents_router
from backend.app.api.v1.rag import rag_router
from backend.app.api.v1.security import security_router
from backend.app.api.v1.tools import tools_router
from backend.app.api.v1.approvals import approvals_router
from backend.app.api.v1.evaluations import evaluations_router
from backend.app.api.v1.dashboard import dashboard_router
from backend.app.api.v1.agents import router as agents_router
from backend.app.api.v1.traces import router as traces_router

api_v1_router = APIRouter(prefix="/v1")

# Subsystem Routers
api_v1_router.include_router(dashboard_router)
api_v1_router.include_router(agents_router)
api_v1_router.include_router(traces_router)
api_v1_router.include_router(evaluations_router)
api_v1_router.include_router(security_router)
api_v1_router.include_router(tools_router)
api_v1_router.include_router(approvals_router)
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
                "tool_policy_engine": "ACTIVE",
                "approval_engine": "ACTIVE",
                "evaluation_engine": "ACTIVE",
                "dashboard_analytics": "ACTIVE",
                "mock_provider": "READY",
                "rag_engine": "ACTIVE",
                "qdrant_store": "INITIALIZED",
            }
        }
    )
