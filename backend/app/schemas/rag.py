from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DocumentChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    chunk_index: int
    content: str
    token_count: int
    page_number: Optional[int] = None
    start_char: int
    end_char: int
    created_at: datetime


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    filename: str
    file_type: str
    file_size_bytes: int
    content_hash: str
    status: str
    error_message: Optional[str] = None
    total_chunks: int
    total_tokens: int
    doc_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class DocumentDetailRead(DocumentRead):
    chunks: List[DocumentChunkRead] = []


class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    tenant_id: str
    document_id_filter: Optional[str] = None
    max_retries: int = Field(default=2, ge=0, le=5)


class CitationItemSchema(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    page_number: Optional[int] = None
    relevant_source_text: str


class RAGQueryResponse(BaseModel):
    query: str
    rewritten_query: str
    answer: str
    groundedness_verdict: str  # GROUNDED, UNGROUNDED, INSUFFICIENT_EVIDENCE
    retrieval_grade: str  # SUFFICIENT, POOR
    retry_count: int
    total_steps: int
    citations: List[CitationItemSchema] = []
    retrieved_chunk_count: int
    injection_violations: List[Dict[str, Any]] = []
    retrieval_event_id: Optional[str] = None
    is_mock: bool = True


class RetrievalEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    query: str
    rewritten_query: Optional[str] = None
    retry_count: int
    is_relevant: bool
    grader_reasoning: Optional[str] = None
    groundedness_verdict: Optional[str] = None
    retrieved_chunks: Optional[Any] = None
    created_at: datetime
