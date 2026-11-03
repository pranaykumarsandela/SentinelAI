import json
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.rag.service import rag_service
from backend.app.schemas.common import APIResponse, PaginatedResponse
from backend.app.schemas.rag import DocumentRead, DocumentDetailRead

documents_router = APIRouter(prefix="/documents", tags=["Documents"])


@documents_router.post("/upload", response_model=APIResponse[DocumentRead], status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    tenant_id: str = Form(...),
    metadata: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload and ingest a document into the RAG subsystem.
    Supports PDF, TXT, Markdown, and DOCX.
    Extracts text, chunks, computes embeddings, and indexes in Qdrant and relational database.
    """
    content_bytes = await file.read()
    if not content_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes)."
        )

    parsed_metadata = {}
    if metadata:
        try:
            parsed_metadata = json.loads(metadata)
        except Exception:
            parsed_metadata = {"raw": metadata}

    try:
        doc = await rag_service.ingest_document(
            session=db,
            tenant_id=tenant_id,
            filename=file.filename or "uploaded_document",
            content_bytes=content_bytes,
            metadata=parsed_metadata,
        )
        return APIResponse(
            success=True,
            message=f"Document '{doc.filename}' successfully ingested ({doc.total_chunks} chunks indexed)",
            data=DocumentRead.model_validate(doc)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to ingest document: {str(e)}"
        )


@documents_router.get("", response_model=APIResponse[PaginatedResponse[DocumentRead]])
async def list_documents(
    tenant_id: str = Query(..., description="Tenant ID to filter documents"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all ingested documents for a tenant with pagination."""
    docs, total = await rag_service.list_documents(db, tenant_id=tenant_id, page=page, page_size=page_size)
    items = [DocumentRead.model_validate(d) for d in docs]
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


@documents_router.get("/{document_id}", response_model=APIResponse[DocumentDetailRead])
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve document details including chunks and ingestion metadata."""
    doc = await rag_service.get_document(db, document_id=document_id, include_chunks=True)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found."
        )
    return APIResponse(
        success=True,
        data=DocumentDetailRead.model_validate(doc)
    )


@documents_router.delete("/{document_id}", response_model=APIResponse[dict])
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete document and its indexed vectors from relational DB and Qdrant."""
    deleted = await rag_service.delete_document(db, document_id=document_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found."
        )
    return APIResponse(
        success=True,
        message=f"Document '{document_id}' and all associated vector chunks successfully deleted.",
        data={"deleted_document_id": document_id}
    )

