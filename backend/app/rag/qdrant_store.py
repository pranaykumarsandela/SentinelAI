import uuid
from typing import Any, Dict, List, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from backend.app.core.config import settings


def to_qdrant_uuid(point_id: str) -> str:
    """Ensures point ID is a valid RFC 4122 UUID acceptable by Qdrant."""
    try:
        return str(uuid.UUID(str(point_id)))
    except ValueError:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, str(point_id)))


class QdrantVectorStore:
    """
    Qdrant Vector Database Adapter for SentinelAI RAG.
    Supports in-memory operation for tests and isolated deployments,
    and network connection for enterprise production.
    """

    COLLECTION_NAME = "sentinel_rag_documents"
    VECTOR_DIM = 384

    def __init__(self):
        if settings.QDRANT_IN_MEMORY:
            self.client = QdrantClient(":memory:")
        else:
            self.client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Creates the collection if not already initialized."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.COLLECTION_NAME for c in collections)
        if not exists:
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=qmodels.VectorParams(
                    size=self.VECTOR_DIM,
                    distance=qmodels.Distance.COSINE
                ),
            )

    def upsert_chunks(
        self,
        tenant_id: str,
        document_id: str,
        filename: str,
        chunks: List[Dict[str, Any]],
        vectors: List[List[float]],
    ) -> int:
        """Upsert a batch of document chunks and their dense vectors into Qdrant."""
        points = []
        for chunk, vector in zip(chunks, vectors):
            point_id = to_qdrant_uuid(chunk["chunk_id"])
            payload = {
                "chunk_id": str(chunk["chunk_id"]),
                "document_id": str(document_id),
                "tenant_id": str(tenant_id),
                "filename": filename,
                "page_number": chunk.get("page_number"),
                "chunk_index": chunk.get("chunk_index", 0),
                "token_count": chunk.get("token_count", 0),
                "content": chunk["content"],
                "start_char": chunk.get("start_char", 0),
                "end_char": chunk.get("end_char", 0),
            }
            points.append(
                qmodels.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload
                )
            )

        if points:
            self.client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=points
            )
        return len(points)

    def search_dense(
        self,
        query_vector: List[float],
        tenant_id: Optional[str] = None,
        document_id: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Dense cosine vector search against Qdrant collection."""
        filter_conditions = []
        if tenant_id:
            filter_conditions.append(
                qmodels.FieldCondition(
                    key="tenant_id",
                    match=qmodels.MatchValue(value=tenant_id)
                )
            )
        if document_id:
            filter_conditions.append(
                qmodels.FieldCondition(
                    key="document_id",
                    match=qmodels.MatchValue(value=document_id)
                )
            )

        query_filter = qmodels.Filter(must=filter_conditions) if filter_conditions else None

        results = self.client.query_points(
            collection_name=self.COLLECTION_NAME,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True
        ).points

        output = []
        for pt in results:
            payload = pt.payload or {}
            output.append({
                "chunk_id": payload.get("chunk_id", str(pt.id)),
                "score": float(pt.score),  # Genuine cosine similarity score from Qdrant
                "content": payload.get("content", ""),
                "document_id": payload.get("document_id", ""),
                "filename": payload.get("filename", ""),
                "page_number": payload.get("page_number"),
                "chunk_index": payload.get("chunk_index", 0),
                "token_count": payload.get("token_count", 0),
                "tenant_id": payload.get("tenant_id", ""),
            })
        return output

    def delete_document_points(self, document_id: str) -> None:
        """Deletes all chunks belonging to a document from Qdrant."""
        self.client.delete(
            collection_name=self.COLLECTION_NAME,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="document_id",
                            match=qmodels.MatchValue(value=document_id)
                        )
                    ]
                )
            )
        )


qdrant_store = QdrantVectorStore()
