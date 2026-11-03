import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel
from backend.app.rag.hybrid_retriever import CrossEncoderReranker


class RAGASSample(BaseModel):
    sample_id: str
    question: str
    contexts: List[str]
    answer: str
    ground_truth: Optional[str] = None
    relevant_doc_ids: Optional[List[str]] = None


class RAGASMetricResult(BaseModel):
    faithfulness: Optional[float] = None
    faithfulness_reason: Optional[str] = None
    answer_relevancy: Optional[float] = None
    answer_relevancy_reason: Optional[str] = None
    context_precision: Optional[float] = None
    context_precision_reason: Optional[str] = None
    context_recall: Optional[float] = None
    context_recall_reason: Optional[str] = None


class RAGASEvaluationEngine:
    """
    Deterministic & Objective RAGAS Evaluation Engine.
    Strictly calculates real mathematical scores from actual inputs.
    Never fabricates scores. If a metric cannot be evaluated, returns None with an honest reason.
    """

    def __init__(self):
        self.reranker = CrossEncoderReranker()

    def _split_into_sentences(self, text: str) -> List[str]:
        """Extracts meaningful factual sentences/propositions from text."""
        if not text:
            return []
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        return [s.strip() for s in sentences if len(s.strip()) > 5]

    def _statement_supported_by_context(self, statement: str, context_text: str) -> bool:
        """Determines if a factual statement is grounded in the retrieved context."""
        s_words = [w for w in re.findall(r"\w+", statement.lower()) if len(w) > 3]
        if not s_words:
            return True
        c_words = set(w for w in re.findall(r"\w+", context_text.lower()))
        c_stems = set(w[:3] for w in c_words)

        # Match exact words or 3-character morphological roots
        overlap = sum(1 for w in s_words if w in c_words or w[:3] in c_stems)
        return (overlap / len(s_words)) >= 0.50

    def calculate_faithfulness(self, answer: str, contexts: List[str]) -> Tuple[Optional[float], Optional[str]]:
        """
        Faithfulness: Measures whether the claims made in the answer are grounded in the context.
        Score = (Supported claims in answer) / (Total claims in answer).
        """
        if not contexts or not any(c.strip() for c in contexts):
            return None, "N/A: Retrieved context is empty; cannot evaluate grounding."

        statements = self._split_into_sentences(answer)
        if not statements:
            return None, "N/A: Generated answer contains no evaluable factual sentences."

        joined_context = " ".join(contexts)
        supported_count = sum(1 for s in statements if self._statement_supported_by_context(s, joined_context))
        score = round(supported_count / len(statements), 4)
        reason = f"Verified {supported_count} of {len(statements)} answer propositions supported by context."
        return score, reason

    def calculate_answer_relevancy(self, question: str, answer: str) -> Tuple[Optional[float], Optional[str]]:
        """
        Answer Relevancy: Evaluates how directly the answer addresses the question.
        Combines cross-encoder semantic interaction with query intent root coverage.
        """
        if not question or not answer:
            return None, "N/A: Question or answer is empty."

        stopwords = {"what", "is", "the", "for", "how", "to", "can", "you", "tell", "me", "about", "a", "an", "of", "in"}
        q_words = [w for w in re.findall(r"\w+", question.lower()) if w not in stopwords and len(w) > 2]
        a_words = set(re.findall(r"\w+", answer.lower()))
        a_stems = set(w[:3] for w in a_words)

        if not q_words:
            coverage = 0.5
        else:
            matches = sum(1 for w in q_words if w in a_words or w[:3] in a_stems)
            coverage = matches / len(q_words)

        # Cross-encoder interaction
        ce_score = self.reranker.score(question, answer)

        relevancy_score = round(max(0.0, min(1.0, (coverage * 0.5) + (ce_score * 0.7))), 4)
        reason = f"Computed cross-encoder alignment ({ce_score:.2f}) and query root coverage ({coverage:.2f})."
        return relevancy_score, reason

    def calculate_context_precision(
        self,
        question: str,
        contexts: List[str],
        ground_truth: Optional[str] = None
    ) -> Tuple[Optional[float], Optional[str]]:
        """
        Context Precision: Evaluates whether relevant knowledge appears at higher ranks.
        Computes Mean Average Precision (MAP) at rank K.
        """
        if not contexts:
            return None, "N/A: Context list is empty."
        if not ground_truth:
            return None, "N/A: Ground-truth reference is missing; cannot evaluate context precision."

        gt_words = [w for w in re.findall(r"\w+", ground_truth.lower()) if len(w) > 3]
        if not gt_words:
            return None, "N/A: Ground-truth contains no substantive tokens."

        precisions = []
        relevant_chunks_found = 0

        for k, ctx in enumerate(contexts):
            ctx_words = set(re.findall(r"\w+", ctx.lower()))
            ctx_stems = set(w[:3] for w in ctx_words)
            overlap = sum(1 for w in gt_words if w in ctx_words or w[:3] in ctx_stems)
            is_relevant = (overlap / len(gt_words)) >= 0.40

            if is_relevant:
                relevant_chunks_found += 1
                precision_at_k = relevant_chunks_found / (k + 1)
                precisions.append(precision_at_k)

        if relevant_chunks_found == 0:
            return 0.0, "None of the retrieved context chunks matched the ground-truth criteria."

        avg_precision = round(sum(precisions) / relevant_chunks_found, 4)
        reason = f"Ranked {relevant_chunks_found} relevant chunk(s) across {len(contexts)} candidates (MAP: {avg_precision})."
        return avg_precision, reason

    def calculate_context_recall(
        self,
        ground_truth: Optional[str],
        contexts: List[str]
    ) -> Tuple[Optional[float], Optional[str]]:
        """
        Context Recall: Evaluates what proportion of ground-truth propositions are captured in retrieved context.
        """
        if not ground_truth:
            return None, "N/A: Ground-truth reference is missing; cannot evaluate context recall."
        if not contexts:
            return 0.0, "Zero context chunks retrieved; context recall is 0.0."

        gt_sentences = self._split_into_sentences(ground_truth)
        if not gt_sentences:
            return None, "N/A: Ground-truth contains no distinct sentences."

        joined_context = " ".join(contexts)
        recalled_count = sum(1 for s in gt_sentences if self._statement_supported_by_context(s, joined_context))

        score = round(recalled_count / len(gt_sentences), 4)
        reason = f"Captured {recalled_count} of {len(gt_sentences)} ground-truth sentences in retrieved context."
        return score, reason

    def evaluate_sample(self, sample: RAGASSample) -> RAGASMetricResult:
        """Evaluates all 4 RAGAS metrics for an individual test sample."""
        f_score, f_reason = self.calculate_faithfulness(sample.answer, sample.contexts)
        r_score, r_reason = self.calculate_answer_relevancy(sample.question, sample.answer)
        p_score, p_reason = self.calculate_context_precision(sample.question, sample.contexts, sample.ground_truth)
        rec_score, rec_reason = self.calculate_context_recall(sample.ground_truth, sample.contexts)

        return RAGASMetricResult(
            faithfulness=f_score,
            faithfulness_reason=f_reason,
            answer_relevancy=r_score,
            answer_relevancy_reason=r_reason,
            context_precision=p_score,
            context_precision_reason=p_reason,
            context_recall=rec_score,
            context_recall_reason=rec_reason
        )


ragas_engine = RAGASEvaluationEngine()
