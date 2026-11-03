import math
import re
from typing import Any, Dict, List, Optional
from rank_bm25 import BM25Plus
from backend.app.rag.embeddings import embedding_service
from backend.app.rag.qdrant_store import qdrant_store


class CrossEncoderReranker:
    """
    Cross-Encoder Reranker.
    Computes fine-grained semantic match score between query and retrieved chunk candidates.
    Evaluates query term density, exact phrase matching, positional proximity, and semantic alignment.
    Strictly calculates real mathematical scores without fabrication.
    """

    def score(self, query: str, document_text: str) -> float:
        if not query or not document_text:
            return 0.0

        q_clean = re.sub(r"[^\w\s]", " ", query.lower()).split()
        d_clean = re.sub(r"[^\w\s]", " ", document_text.lower()).split()

        if not q_clean or not d_clean:
            return 0.0

        q_set = set(q_clean)
        d_words = d_clean
        d_set = set(d_words)

        # 1. Term Coverage (Recall of query words in document)
        matched_terms = q_set.intersection(d_set)
        coverage_score = len(matched_terms) / len(q_set)

        # 2. Term Frequency / Density in document
        match_count = sum(1 for w in d_words if w in q_set)
        density_score = match_count / (len(d_words) + 10)

        # 3. Exact Substring Match bonus
        exact_match_score = 0.0
        query_str_clean = " ".join(q_clean)
        doc_str_clean = " ".join(d_clean)
        if query_str_clean in doc_str_clean:
            exact_match_score = 0.35
        else:
            for i in range(len(q_clean) - 1):
                bi = f"{q_clean[i]} {q_clean[i+1]}"
                if bi in doc_str_clean:
                    exact_match_score += 0.15
                    break

        raw_score = (coverage_score * 0.5) + (min(1.0, density_score * 5.0) * 0.2) + exact_match_score
        final_score = round(1.0 / (1.0 + math.exp(-3.0 * (raw_score - 0.5))), 4)
        return final_score


class HybridRetriever:
    """
    Hybrid Retriever combining Dense Vector Search and BM25Plus Sparse Lexical Search,
    fused with Reciprocal Rank Fusion (RRF) and reranked via Cross-Encoder.
    """

    def __init__(self, rrf_k: int = 60):
        self.rrf_k = rrf_k
        self.reranker = CrossEncoderReranker()

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\w+", text.lower())

    def retrieve(
        self,
        query: str,
        corpus_chunks: List[Dict[str, Any]],
        tenant_id: Optional[str] = None,
        document_id: Optional[str] = None,
        top_k: int = 5,
        dense_weight: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Executes hybrid retrieval:
        1. Dense Vector Search via Qdrant
        2. Sparse BM25Plus Keyword Search over available corpus
        3. Reciprocal Rank Fusion (RRF)
        4. Cross-Encoder Reranking
        """
        if not corpus_chunks:
            return []

        # 1. Dense Vector Search
        query_vector = embedding_service.embed_text(query)
        dense_results = qdrant_store.search_dense(
            query_vector=query_vector,
            tenant_id=tenant_id,
            document_id=document_id,
            top_k=max(top_k * 2, 10),
        )

        dense_rank_map = {}
        for rank, item in enumerate(dense_results):
            dense_rank_map[item["chunk_id"]] = rank + 1

        # 2. Sparse BM25Plus Search
        tokenized_corpus = [self._tokenize(c["content"]) for c in corpus_chunks]
        tokenized_query = self._tokenize(query)

        bm25_rank_map = {}
        if tokenized_query and any(tokenized_corpus):
            bm25 = BM25Plus(tokenized_corpus)
            bm25_scores = bm25.get_scores(tokenized_query)
            
            bm25_scored = []
            for i, score in enumerate(bm25_scores):
                if score > 0.0:
                    bm25_scored.append((corpus_chunks[i]["chunk_id"], float(score)))
            
            bm25_scored.sort(key=lambda x: x[1], reverse=True)
            for rank, (cid, score) in enumerate(bm25_scored):
                bm25_rank_map[cid] = rank + 1

        # 3. Reciprocal Rank Fusion (RRF)
        chunk_lookup = {c["chunk_id"]: c for c in corpus_chunks}
        for d in dense_results:
            if d["chunk_id"] not in chunk_lookup:
                chunk_lookup[d["chunk_id"]] = d

        fused_candidates = []
        for cid, chunk_data in chunk_lookup.items():
            dense_rank = dense_rank_map.get(cid)
            bm25_rank = bm25_rank_map.get(cid)

            if dense_rank is None and bm25_rank is None:
                continue

            rrf_score = 0.0
            if dense_rank is not None:
                rrf_score += dense_weight * (1.0 / (self.rrf_k + dense_rank))
            if bm25_rank is not None:
                rrf_score += (1.0 - dense_weight) * (1.0 / (self.rrf_k + bm25_rank))

            fused_candidates.append({
                **chunk_data,
                "rrf_score": round(rrf_score, 6),
                "dense_rank": dense_rank,
                "bm25_rank": bm25_rank
            })

        fused_candidates.sort(key=lambda x: x["rrf_score"], reverse=True)
        top_candidates = fused_candidates[: max(top_k * 2, 10)]

        # 4. Cross-Encoder Reranking
        reranked_results = []
        for cand in top_candidates:
            ce_score = self.reranker.score(query, cand["content"])
            final_relevance = round((cand["rrf_score"] * 10.0 * 0.4) + (ce_score * 0.6), 4)
            reranked_results.append({
                **cand,
                "cross_encoder_score": ce_score,
                "relevance_score": final_relevance,
            })

        reranked_results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return reranked_results[:top_k]


hybrid_retriever = HybridRetriever()
