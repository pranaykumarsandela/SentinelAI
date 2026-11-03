from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.rag.service import rag_service
from backend.app.schemas.common import APIResponse, PaginatedResponse
from backend.app.schemas.rag import RAGQueryRequest, RAGQueryResponse, RetrievalEventRead

rag_router = APIRouter(prefix="/rag", tags=["RAG"])


@rag_router.post("/query", response_model=APIResponse[RAGQueryResponse])
async def query_rag_pipeline(
    payload: RAGQueryRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Execute full Agentic RAG pipeline:
    - Query analysis
    - Retrieval decision
    - Hybrid dense + BM25 retrieval
    - Retrieval grading
    - Query rewriting upon poor retrieval
    - Indirect prompt injection defense
    - Grounded answer synthesis with real verified citations
    - Groundedness check
    """
    try:
        result = await rag_service.query_rag(
            session=db,
            tenant_id=payload.tenant_id,
            query=payload.query,
            document_id_filter=payload.document_id_filter,
            max_retries=payload.max_retries,
        )
        return APIResponse(
            success=True,
            message="RAG query executed successfully",
            data=RAGQueryResponse(**result)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agentic RAG execution failed: {str(e)}"
        )


@rag_router.get("/retrievals", response_model=APIResponse[PaginatedResponse[RetrievalEventRead]])
async def list_retrieval_events(
    tenant_id: str = Query(..., description="Tenant ID to filter retrieval events"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve historical RAG retrieval audit records."""
    events, total = await rag_service.list_retrieval_events(
        session=db,
        tenant_id=tenant_id,
        page=page,
        page_size=page_size
    )
    items = [RetrievalEventRead.model_validate(e) for e in events]
    return APIResponse(
        success=True,
        data=PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=(page * page_size < total)
        )
    )

