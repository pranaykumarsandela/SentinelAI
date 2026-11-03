import hashlib
import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.entities import (
    Document,
    DocumentChunk,
    RetrievalEvent,
    IngestionStatus,
)
from backend.app.rag.document_loaders import DocumentLoader, ExtractedDocument
from backend.app.rag.chunking import DocumentChunker, ChunkItem
from backend.app.rag.embeddings import embedding_service
from backend.app.rag.qdrant_store import qdrant_store
from backend.app.rag.agentic_graph import agentic_rag_graph


class RAGService:
    """Enterprise Agentic RAG Service."""

    def __init__(self):
        self.chunker = DocumentChunker(chunk_size=500, chunk_overlap=80)

    async def ingest_document(
        self,
        session: AsyncSession,
        tenant_id: str,
        filename: str,
        content_bytes: bytes,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Document:
        """
        Executes end-to-end ingestion pipeline:
        1. Validates file format and size
        2. Computes SHA-256 hash
        3. Extracts text and page metadata
        4. Chunks content
        5. Generates embeddings
        6. Persists Document & Chunks in DB
        7. Indexes vectors into Qdrant
        """
        content_hash = hashlib.sha256(content_bytes).hexdigest()
        file_type = DocumentLoader.validate_file(filename, content_bytes)

        # Create Document record in DB with PENDING status
        doc = Document(
            tenant_id=tenant_id,
            filename=filename,
            file_type=file_type,
            file_size_bytes=len(content_bytes),
            content_hash=content_hash,
            status=IngestionStatus.PROCESSING.value,
            doc_metadata=metadata or {},
        )
        session.add(doc)
        await session.flush()
        await session.refresh(doc)

        try:
            # Extract Text & Pages
            extracted = DocumentLoader.load_bytes(filename, content_bytes, content_hash)

            # Chunk Document
            chunks: List[ChunkItem] = self.chunker.chunk_document(doc.id, extracted)
            if not chunks:
                raise ValueError(f"No chunks could be produced from document '{filename}'")

            # Generate Embeddings
            chunk_texts = [c.content for c in chunks]
            vectors = embedding_service.embed_batch(chunk_texts)

            # Persist Chunks in Relational Database
            db_chunks = []
            qdrant_chunk_payloads = []
            total_tokens = 0

            for chunk_item in chunks:
                total_tokens += chunk_item.token_count
                db_chunk = DocumentChunk(
                    id=chunk_item.chunk_id,
                    document_id=doc.id,
                    chunk_index=chunk_item.chunk_index,
                    content=chunk_item.content,
                    token_count=chunk_item.token_count,
                    page_number=chunk_item.page_number,
                    start_char=chunk_item.start_char,
                    end_char=chunk_item.end_char,
                    qdrant_point_id=chunk_item.chunk_id,
                    chunk_metadata={
                        "filename": filename,
                        "page_number": chunk_item.page_number,
                    },
                )
                db_chunks.append(db_chunk)
                qdrant_chunk_payloads.append({
                    "chunk_id": chunk_item.chunk_id,
                    "content": chunk_item.content,
                    "page_number": chunk_item.page_number,
                    "chunk_index": chunk_item.chunk_index,
                    "token_count": chunk_item.token_count,
                    "start_char": chunk_item.start_char,
                    "end_char": chunk_item.end_char,
                })

            session.add_all(db_chunks)

            # Upsert into Qdrant Vector Collection
            qdrant_store.upsert_chunks(
                tenant_id=tenant_id,
                document_id=doc.id,
                filename=filename,
                chunks=qdrant_chunk_payloads,
                vectors=vectors
            )

            # Update Document status to COMPLETED
            doc.status = IngestionStatus.COMPLETED.value
            doc.total_chunks = len(chunks)
            doc.total_tokens = total_tokens
            await session.commit()
            await session.refresh(doc)
            return doc

        except Exception as e:
            doc.status = IngestionStatus.FAILED.value
            doc.error_message = str(e)
            await session.commit()
            await session.refresh(doc)
            raise

    async def list_documents(
        self,
        session: AsyncSession,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Document], int]:
        """Lists tenant documents with pagination."""
        offset = (page - 1) * page_size
        
        # Total count
        count_stmt = select(Document).where(Document.tenant_id == tenant_id)
        count_res = await session.execute(count_stmt)
        total = len(count_res.scalars().all())

        # Paginated fetch
        stmt = (
            select(Document)
            .where(Document.tenant_id == tenant_id)
            .order_by(desc(Document.created_at))
            .offset(offset)
            .limit(page_size)
        )
        res = await session.execute(stmt)
        docs = list(res.scalars().all())
        return docs, total

    async def get_document(
        self,
        session: AsyncSession,
        document_id: str,
        include_chunks: bool = True,
    ) -> Optional[Document]:
        """Retrieves document details with chunks if requested."""
        if include_chunks:
            stmt = select(Document).options(selectinload(Document.chunks)).where(Document.id == document_id)
        else:
            stmt = select(Document).where(Document.id == document_id)
            
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def delete_document(self, session: AsyncSession, document_id: str) -> bool:
        """Deletes document and chunks from database and Qdrant."""
        doc = await self.get_document(session, document_id, include_chunks=False)
        if not doc:
            return False

        # 1. Delete points from Qdrant
        qdrant_store.delete_document_points(document_id)

        # 2. Delete from database (cascades chunks)
        await session.delete(doc)
        await session.commit()
        return True

    async def query_rag(
        self,
        session: AsyncSession,
        tenant_id: str,
        query: str,
        document_id_filter: Optional[str] = None,
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        """
        Executes Agentic RAG pipeline:
        1. Loads tenant document chunks from database
        2. Invokes compiled LangGraph agentic graph
        3. Persists audit RetrievalEvent
        4. Returns structured output
        """
        # Load available corpus chunks from database
        stmt = (
            select(DocumentChunk, Document.filename)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(Document.tenant_id == tenant_id, Document.status == IngestionStatus.COMPLETED.value)
        )
        if document_id_filter:
            stmt = stmt.where(Document.id == document_id_filter)

        res = await session.execute(stmt)
        rows = res.all()

        corpus_chunks = []
        for chunk, filename in rows:
            corpus_chunks.append({
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "filename": filename,
                "content": chunk.content,
                "page_number": chunk.page_number,
                "chunk_index": chunk.chunk_index,
                "token_count": chunk.token_count,
            })

        # Run LangGraph StateGraph
        initial_state = {
            "query": query,
            "tenant_id": tenant_id,
            "document_id_filter": document_id_filter,
            "corpus_chunks": corpus_chunks,
            "rewritten_query": query,
            "retry_count": 0,
            "max_retries": max_retries,
            "step_count": 0,
            "max_steps": 12,
            "retrieved_chunks": [],
            "sanitized_chunks": [],
            "injection_violations": [],
            "retrieval_grade": "PENDING",
            "grader_reasoning": "",
            "context_valid": False,
            "answer": "",
            "groundedness_verdict": "INSUFFICIENT_EVIDENCE",
            "citations": [],
            "error": None,
            "final_output": {}
        }

        graph_result = agentic_rag_graph.invoke(initial_state)
        final_output = graph_result.get("final_output", {})

        # Persist RetrievalEvent for database audit trail
        retrieval_event = RetrievalEvent(
            tenant_id=tenant_id,
            query=query,
            rewritten_query=final_output.get("rewritten_query"),
            retry_count=final_output.get("retry_count", 0),
            is_relevant=(final_output.get("retrieval_grade") == "SUFFICIENT"),
            grader_reasoning=graph_result.get("grader_reasoning"),
            groundedness_verdict=final_output.get("groundedness_verdict"),
            retrieved_chunks=final_output.get("citations"),
        )
        session.add(retrieval_event)
        await session.commit()
        await session.refresh(retrieval_event)

        final_output["retrieval_event_id"] = retrieval_event.id
        return final_output

    async def list_retrieval_events(
        self,
        session: AsyncSession,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[RetrievalEvent], int]:
        """Lists historical retrieval audit events."""
        offset = (page - 1) * page_size
        
        count_stmt = select(RetrievalEvent).where(RetrievalEvent.tenant_id == tenant_id)
        count_res = await session.execute(count_stmt)
        total = len(count_res.scalars().all())

        stmt = (
            select(RetrievalEvent)
            .where(RetrievalEvent.tenant_id == tenant_id)
            .order_by(desc(RetrievalEvent.created_at))
            .offset(offset)
            .limit(page_size)
        )
        res = await session.execute(stmt)
        events = list(res.scalars().all())
        return events, total


rag_service = RAGService()

