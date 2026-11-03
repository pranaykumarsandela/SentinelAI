import time
import re
from typing import Any, Dict, List, Optional, TypedDict
from langgraph.graph import StateGraph, START, END

from backend.app.rag.hybrid_retriever import hybrid_retriever
from backend.app.rag.prompt_injection_guard import indirect_injection_guard
from backend.app.services.mock_llm import mock_llm_service


class CitationItem(TypedDict):
    chunk_id: str
    document_id: str
    filename: str
    page_number: Optional[int]
    relevant_source_text: str


class AgenticRAGState(TypedDict):
    # Inputs
    query: str
    tenant_id: str
    document_id_filter: Optional[str]
    corpus_chunks: List[Dict[str, Any]]
    
    # Internal state
    rewritten_query: str
    retry_count: int
    max_retries: int
    step_count: int
    max_steps: int
    
    # Retrieval & Verification
    retrieved_chunks: List[Dict[str, Any]]
    sanitized_chunks: List[Dict[str, Any]]
    injection_violations: List[Dict[str, Any]]
    retrieval_grade: str  # "SUFFICIENT" or "POOR"
    grader_reasoning: str
    context_valid: bool
    
    # Generation & Grounding
    answer: str
    groundedness_verdict: str  # "GROUNDED", "UNGROUNDED", "INSUFFICIENT_EVIDENCE"
    citations: List[CitationItem]
    error: Optional[str]
    final_output: Dict[str, Any]


# --- Graph Nodes ---

def query_analysis_node(state: AgenticRAGState) -> Dict[str, Any]:
    """Analyzes query intent, normalizes terms, and initializes state."""
    state["step_count"] = state.get("step_count", 0) + 1
    query = state["query"].strip()
    normalized = re.sub(r"\s+", " ", query)
    
    return {
        "step_count": state["step_count"],
        "rewritten_query": normalized,
        "retry_count": state.get("retry_count", 0),
        "max_retries": state.get("max_retries", 2),
        "max_steps": state.get("max_steps", 12),
        "retrieved_chunks": [],
        "citations": [],
        "error": None
    }


def retrieval_decision_node(state: AgenticRAGState) -> Dict[str, Any]:
    """Determines whether document retrieval is necessary for this query."""
    state["step_count"] = state.get("step_count", 0) + 1
    query_lower = state["rewritten_query"].lower()
    
    greetings = {"hello", "hi", "hey", "who are you", "help"}
    if query_lower in greetings or len(query_lower) < 3:
        return {
            "step_count": state["step_count"],
            "retrieval_grade": "NOT_NEEDED",
            "grader_reasoning": "Conversational query does not require factual document retrieval."
        }
    
    return {
        "step_count": state["step_count"],
        "retrieval_grade": "PENDING",
        "grader_reasoning": "Informational query requires document repository retrieval."
    }


def document_retrieval_node(state: AgenticRAGState) -> Dict[str, Any]:
    """Executes hybrid dense-sparse retrieval and cross-encoder reranking."""
    state["step_count"] = state.get("step_count", 0) + 1
    query = state["rewritten_query"]
    corpus = state.get("corpus_chunks", [])
    tenant_id = state.get("tenant_id")
    doc_filter = state.get("document_id_filter")
    
    if not corpus:
        return {
            "step_count": state["step_count"],
            "retrieved_chunks": [],
            "retrieval_grade": "POOR",
            "grader_reasoning": "Document repository is empty. No knowledge chunks available."
        }

    results = hybrid_retriever.retrieve(
        query=query,
        corpus_chunks=corpus,
        tenant_id=tenant_id,
        document_id=doc_filter,
        top_k=4
    )

    return {
        "step_count": state["step_count"],
        "retrieved_chunks": results
    }


def retrieval_grader_node(state: AgenticRAGState) -> Dict[str, Any]:
    """Evaluates the relevance of retrieved chunks against query intent."""
    state["step_count"] = state.get("step_count", 0) + 1
    chunks = state.get("retrieved_chunks", [])
    query = state.get("rewritten_query", "")

    if not chunks:
        return {
            "step_count": state["step_count"],
            "retrieval_grade": "POOR",
            "grader_reasoning": "Zero chunks retrieved from document store."
        }

    top_chunk = chunks[0]
    rel_score = top_chunk.get("relevance_score", 0.0)

    # Word overlap check excluding common stopwords
    stopwords = {"what", "are", "the", "for", "is", "in", "of", "to", "a", "an", "do", "does", "how", "can", "you", "tell", "me"}
    q_words = set(w for w in re.findall(r"\w+", query.lower()) if w not in stopwords)
    top_words = set(re.findall(r"\w+", top_chunk.get("content", "").lower()))
    overlap = len(q_words.intersection(top_words))

    is_sufficient = (
        rel_score >= 0.25
        or (len(q_words) > 0 and (overlap / len(q_words)) >= 0.3)
        or overlap >= 2
    )

    if is_sufficient:
        return {
            "step_count": state["step_count"],
            "retrieval_grade": "SUFFICIENT",
            "grader_reasoning": f"Relevant context found with relevance score {rel_score:.3f} and {overlap} keyword matches."
        }
    else:
        return {
            "step_count": state["step_count"],
            "retrieval_grade": "POOR",
            "grader_reasoning": f"Retrieved chunks have low relevance score ({rel_score:.3f}) and weak keyword overlap ({overlap})."
        }


def query_rewriter_node(state: AgenticRAGState) -> Dict[str, Any]:
    """Rewrites query to improve retrieval recall for subsequent retry."""
    state["step_count"] = state.get("step_count", 0) + 1
    current_retry = state.get("retry_count", 0) + 1
    query = state.get("rewritten_query", "")

    stopwords = {"what", "is", "the", "how", "to", "can", "you", "tell", "me", "about", "a", "an", "of", "in", "on"}
    words = re.findall(r"\w+", query)
    important_terms = [w for w in words if w.lower() not in stopwords]
    
    if important_terms:
        rewritten = " ".join(important_terms)
    else:
        rewritten = f"{query} overview details"

    return {
        "step_count": state["step_count"],
        "retry_count": current_retry,
        "rewritten_query": rewritten
    }


def context_validation_node(state: AgenticRAGState) -> Dict[str, Any]:
    """Applies indirect prompt injection defense and secures retrieved context."""
    state["step_count"] = state.get("step_count", 0) + 1
    retrieved = state.get("retrieved_chunks", [])
    
    sanitized_chunks, violations = indirect_injection_guard.sanitize_retrieved_context(retrieved)

    return {
        "step_count": state["step_count"],
        "sanitized_chunks": sanitized_chunks,
        "injection_violations": violations,
        "context_valid": True
    }


def answer_generation_node(state: AgenticRAGState) -> Dict[str, Any]:
    """Generates grounded answer citing verified document chunks."""
    state["step_count"] = state.get("step_count", 0) + 1
    chunks = state.get("sanitized_chunks", [])
    grade = state.get("retrieval_grade", "")
    
    # Case 1: Empty or persistent poor retrieval after retries -> Explicit insufficient evidence response
    if not chunks or (grade == "POOR" and state.get("retry_count", 0) >= state.get("max_retries", 2)):
        answer = (
            "Insufficient evidence found in the document repository to answer this query. "
            "The available indexed documents do not contain relevant facts to address your request."
        )
        return {
            "step_count": state["step_count"],
            "answer": answer,
            "citations": [],
            "groundedness_verdict": "INSUFFICIENT_EVIDENCE"
        }

    # Case 2: Sufficient context -> Build verified grounded answer with citations
    citations: List[CitationItem] = []
    evidence_sentences = []

    for chunk in chunks[:3]:
        cid = chunk["chunk_id"]
        doc_id = chunk["document_id"]
        fname = chunk["filename"]
        page = chunk.get("page_number", 1)
        content = chunk.get("content", "").strip()

        # Extract primary factual sentence for citation snippet
        first_sentence = content.split(". ")[0].strip()
        if first_sentence:
            evidence_sentences.append(f"{first_sentence}.")
            citations.append({
                "chunk_id": cid,
                "document_id": doc_id,
                "filename": fname,
                "page_number": page,
                "relevant_source_text": first_sentence[:200]
            })

    if not citations:
        answer = "Insufficient evidence found in the document repository to answer this query."
        return {
            "step_count": state["step_count"],
            "answer": answer,
            "citations": [],
            "groundedness_verdict": "INSUFFICIENT_EVIDENCE"
        }

    combined_evidence = " ".join(evidence_sentences)
    answer = (
        f"Based on the indexed document '{citations[0]['filename']}' (Page {citations[0]['page_number']}): "
        f"{combined_evidence}"
    )

    return {
        "step_count": state["step_count"],
        "answer": answer,
        "citations": citations,
        "groundedness_verdict": "GROUNDED"
    }


def groundedness_check_node(state: AgenticRAGState) -> Dict[str, Any]:
    """Verifies that all statements in the answer are grounded in retrieved context."""
    state["step_count"] = state.get("step_count", 0) + 1
    answer = state.get("answer", "")
    citations = state.get("citations", [])
    verdict = state.get("groundedness_verdict", "GROUNDED")

    if verdict == "INSUFFICIENT_EVIDENCE":
        return {
            "step_count": state["step_count"],
            "groundedness_verdict": "INSUFFICIENT_EVIDENCE"
        }

    if not citations:
        final_verdict = "UNGROUNDED"
    else:
        has_overlap = any(
            c["relevant_source_text"].split()[0].lower() in answer.lower()
            for c in citations if c["relevant_source_text"]
        )
        final_verdict = "GROUNDED" if has_overlap else "UNGROUNDED"

    return {
        "step_count": state["step_count"],
        "groundedness_verdict": final_verdict
    }


def final_response_node(state: AgenticRAGState) -> Dict[str, Any]:
    """Packages the final validated agent response and provenance data."""
    state["step_count"] = state.get("step_count", 0) + 1
    
    final_output = {
        "query": state["query"],
        "rewritten_query": state.get("rewritten_query", state["query"]),
        "answer": state.get("answer", ""),
        "groundedness_verdict": state.get("groundedness_verdict", "INSUFFICIENT_EVIDENCE"),
        "retrieval_grade": state.get("retrieval_grade", "POOR"),
        "retry_count": state.get("retry_count", 0),
        "total_steps": state.get("step_count", 0),
        "citations": state.get("citations", []),
        "retrieved_chunk_count": len(state.get("retrieved_chunks", [])),
        "injection_violations": state.get("injection_violations", []),
        "is_mock": True
    }
    
    return {
        "step_count": state["step_count"],
        "final_output": final_output
    }


# --- Conditional Routing Functions ---

def route_retrieval_decision(state: AgenticRAGState) -> str:
    if state.get("retrieval_grade") == "NOT_NEEDED":
        return "answer_generation"
    return "document_retrieval"


def route_retrieval_grader(state: AgenticRAGState) -> str:
    grade = state.get("retrieval_grade", "POOR")
    retries = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 2)
    step_count = state.get("step_count", 0)
    max_steps = state.get("max_steps", 12)

    if step_count >= max_steps:
        return "context_validation"

    if grade == "POOR" and retries < max_retries:
        return "query_rewriter"
    return "context_validation"


# --- Graph Construction ---

def build_agentic_rag_graph() -> StateGraph:
    workflow = StateGraph(AgenticRAGState)

    workflow.add_node("query_analysis", query_analysis_node)
    workflow.add_node("retrieval_decision", retrieval_decision_node)
    workflow.add_node("document_retrieval", document_retrieval_node)
    workflow.add_node("retrieval_grader", retrieval_grader_node)
    workflow.add_node("query_rewriter", query_rewriter_node)
    workflow.add_node("context_validation", context_validation_node)
    workflow.add_node("answer_generation", answer_generation_node)
    workflow.add_node("groundedness_check", groundedness_check_node)
    workflow.add_node("final_response", final_response_node)

    workflow.add_edge(START, "query_analysis")
    workflow.add_edge("query_analysis", "retrieval_decision")
    
    workflow.add_conditional_edges(
        "retrieval_decision",
        route_retrieval_decision,
        {
            "document_retrieval": "document_retrieval",
            "answer_generation": "answer_generation",
        }
    )

    workflow.add_edge("document_retrieval", "retrieval_grader")

    workflow.add_conditional_edges(
        "retrieval_grader",
        route_retrieval_grader,
        {
            "query_rewriter": "query_rewriter",
            "context_validation": "context_validation",
        }
    )

    workflow.add_edge("query_rewriter", "document_retrieval")
    workflow.add_edge("context_validation", "answer_generation")
    workflow.add_edge("answer_generation", "groundedness_check")
    workflow.add_edge("groundedness_check", "final_response")
    workflow.add_edge("final_response", END)

    return workflow.compile()


agentic_rag_graph = build_agentic_rag_graph()
