import time
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from backend.app.models.entities import (
    LLMBenchmarkRun,
    LLMBenchmarkResult,
    utc_now,
)
from backend.app.services.llm_provider import get_llm_provider, LLMProviderError
from backend.app.services.model_router import model_router, PRICING_CATALOG_V1
from backend.app.evaluation.ragas_engine import ragas_engine
from backend.app.observability.logger import sentinel_logger


BENCHMARK_DATASET_V1 = [
    {
        "id": "bench_001",
        "question": "What is the primary role of an asymmetric encryption key pair?",
        "context": "In asymmetric cryptography, a public key encrypts data while the corresponding private key decrypts it. Alternatively, a private key signs a cryptographic digest and the public key verifies it.",
        "ground_truth": "The public key encrypts or verifies, while the private key decrypts or signs.",
    },
    {
        "id": "bench_002",
        "question": "How does SentinelAI isolate indirect prompt injections in retrieved chunks?",
        "context": "SentinelAI inspects retrieved RAG chunks using deterministic heuristic pattern scanners before passing chunks to agent reasoning nodes. Any directive attempting to override system prompts is neutralized.",
        "ground_truth": "By scanning retrieved chunks with heuristic scanners and neutralizing directives before passing context to agent nodes.",
    },
    {
        "id": "bench_003",
        "question": "What is the fail-closed security principle in tool authorization?",
        "context": "Under fail-closed security, if a tool policy is absent or cannot be evaluated, the system defaults to denying execution rather than granting permission.",
        "ground_truth": "The system defaults to denying tool execution if a policy is missing or unavailable.",
    },
    {
        "id": "bench_004",
        "question": "Explain how Reciprocal Rank Fusion combines sparse and dense search results.",
        "context": "RRF combines rankings from BM25 sparse keyword search and dense embedding vector search by assigning scores inversely proportional to rank position plus a constant k.",
        "ground_truth": "By assigning scores based on reciprocal rank position plus a constant k across BM25 and vector search results.",
    },
    {
        "id": "bench_005",
        "question": "What happens when a high-risk tool call requires human supervisor review?",
        "context": "When a tool policy specifies REQUIRE_APPROVAL, the system enters PENDING state, records an approval request, and halts tool execution until an authorized reviewer approves or rejects it.",
        "ground_truth": "The tool call enters PENDING state, creates an approval request, and will not execute until an authorized reviewer approves it.",
    },
]


class ProviderBenchmarkEngine:
    """
    Executes identical benchmark datasets across selected LLM providers.
    Measures authentic latency, tokens, success rate, faithfulness, relevancy,
    and verified cost calculations.
    """

    async def run_benchmark(
        self,
        db: AsyncSession,
        providers_to_test: List[Dict[str, str]],
        dataset_name: str = "SentinelAI Standard Multi-LLM Benchmark",
        dataset_version: str = "v1.0",
        prompt_version: str = "v1.0",
        is_mock: bool = False,
    ) -> LLMBenchmarkRun:
        run_id = str(uuid.uuid4())
        started_at = utc_now()

        pricing_info = {
            "source": PRICING_CATALOG_V1["source"],
            "version": PRICING_CATALOG_V1["version"],
        }

        # Initialize Benchmark Run entity
        run_entity = LLMBenchmarkRun(
            id=run_id,
            dataset_name=dataset_name,
            dataset_version=dataset_version,
            prompt_version=prompt_version,
            selected_providers=providers_to_test,
            total_samples=len(BENCHMARK_DATASET_V1),
            status="RUNNING",
            pricing_source=pricing_info["source"],
            pricing_version=pricing_info["version"],
            started_at=started_at,
        )
        db.add(run_entity)
        await db.commit()

        dataset = BENCHMARK_DATASET_V1

        for target in providers_to_test:
            prov_name = target.get("provider", "mock").lower()
            mod_name = target.get("model", "mock-sentinel-v1")

            provider_inst = get_llm_provider(
                provider_name=prov_name,
                model_name=mod_name,
                is_mock=is_mock or (prov_name == "mock"),
            )

            successful_reqs = 0
            failed_reqs = 0
            latencies: List[float] = []
            prompt_tokens_list: List[int] = []
            completion_tokens_list: List[int] = []
            faithfulness_scores: List[float] = []
            relevancy_scores: List[float] = []
            sample_logs: List[Dict[str, Any]] = []

            for sample in dataset:
                q = sample["question"]
                ctx = sample["context"]
                gt = sample["ground_truth"]

                prompt = f"Context:\n{ctx}\n\nQuestion: {q}\nAnswer the question directly based only on the context."

                start_t = time.perf_counter()
                try:
                    resp = await provider_inst.generate(
                        prompt=prompt,
                        system_prompt="You are a faithful AI evaluation target. Answer truthfully based solely on the provided context.",
                    )
                    lat_ms = resp.latency_ms or round((time.perf_counter() - start_t) * 1000, 2)
                    successful_reqs += 1
                    latencies.append(lat_ms)

                    if resp.input_tokens is not None:
                        prompt_tokens_list.append(resp.input_tokens)
                    if resp.output_tokens is not None:
                        completion_tokens_list.append(resp.output_tokens)

                    # Calculate real evaluation scores
                    ans = resp.response
                    faith, _ = ragas_engine.calculate_faithfulness(ans, [ctx])
                    rel, _ = ragas_engine.calculate_answer_relevancy(q, ans)
                    if faith is not None:
                        faithfulness_scores.append(faith)
                    if rel is not None:
                        relevancy_scores.append(rel)

                    sample_logs.append({
                        "sample_id": sample["id"],
                        "latency_ms": lat_ms,
                        "tokens": resp.total_tokens,
                        "faithfulness": faith,
                        "relevancy": rel,
                        "success": True,
                    })

                except Exception as e:
                    lat_ms = round((time.perf_counter() - start_t) * 1000, 2)
                    failed_reqs += 1
                    latencies.append(lat_ms)
                    sample_logs.append({
                        "sample_id": sample["id"],
                        "latency_ms": lat_ms,
                        "error": str(e),
                        "success": False,
                    })

            # Calculate aggregated metrics
            total_reqs = successful_reqs + failed_reqs
            avg_lat = round(sum(latencies) / len(latencies), 2) if latencies else None
            sorted_lat = sorted(latencies) if latencies else []
            p50_lat = round(sorted_lat[len(sorted_lat) // 2], 2) if sorted_lat else None
            p95_idx = int(len(sorted_lat) * 0.95)
            p95_lat = round(sorted_lat[min(p95_idx, len(sorted_lat) - 1)], 2) if sorted_lat else None

            tot_prompt_tok = sum(prompt_tokens_list) if prompt_tokens_list else None
            tot_comp_tok = sum(completion_tokens_list) if completion_tokens_list else None
            tot_tokens = (tot_prompt_tok or 0) + (tot_comp_tok or 0) if (tot_prompt_tok is not None or tot_comp_tok is not None) else None

            avg_faith = round(sum(faithfulness_scores) / len(faithfulness_scores), 4) if faithfulness_scores else None
            avg_rel = round(sum(relevancy_scores) / len(relevancy_scores), 4) if relevancy_scores else None

            cost = model_router.calculate_cost(mod_name, tot_prompt_tok, tot_comp_tok)
            pricing_data = model_router.get_pricing_metadata(mod_name)

            result_entity = LLMBenchmarkResult(
                id=str(uuid.uuid4()),
                benchmark_run_id=run_id,
                provider=prov_name,
                model=mod_name,
                total_requests=total_reqs,
                successful_requests=successful_reqs,
                failed_requests=failed_reqs,
                avg_latency_ms=avg_lat,
                p50_latency_ms=p50_lat,
                p95_latency_ms=p95_lat,
                total_prompt_tokens=tot_prompt_tok,
                total_completion_tokens=tot_comp_tok,
                total_tokens=tot_tokens,
                faithfulness_score=avg_faith,
                relevancy_score=avg_rel,
                security_score=round(successful_reqs / total_reqs, 4) if total_reqs > 0 else None,
                total_cost_usd=cost,
                pricing_data=pricing_data,
                raw_metrics={"samples": sample_logs},
            )
            db.add(result_entity)

        run_entity.status = "COMPLETED"
        run_entity.completed_at = utc_now()
        await db.commit()
        await db.refresh(run_entity)
        return run_entity

    async def list_benchmark_runs(
        self,
        db: AsyncSession,
        limit: int = 20,
    ) -> List[LLMBenchmarkRun]:
        stmt = (
            select(LLMBenchmarkRun)
            .order_by(desc(LLMBenchmarkRun.started_at))
            .limit(limit)
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    async def get_benchmark_details(
        self,
        db: AsyncSession,
        run_id: str,
    ) -> Optional[Dict[str, Any]]:
        run_entity = await db.get(LLMBenchmarkRun, run_id)
        if not run_entity:
            return None

        stmt = select(LLMBenchmarkResult).where(LLMBenchmarkResult.benchmark_run_id == run_id)
        res = await db.execute(stmt)
        results = list(res.scalars().all())

        return {
            "id": run_entity.id,
            "dataset_name": run_entity.dataset_name,
            "dataset_version": run_entity.dataset_version,
            "prompt_version": run_entity.prompt_version,
            "total_samples": run_entity.total_samples,
            "status": run_entity.status,
            "pricing_source": run_entity.pricing_source,
            "pricing_version": run_entity.pricing_version,
            "started_at": run_entity.started_at.isoformat() if run_entity.started_at else None,
            "completed_at": run_entity.completed_at.isoformat() if run_entity.completed_at else None,
            "results": [
                {
                    "provider": r.provider,
                    "model": r.model,
                    "total_requests": r.total_requests,
                    "successful_requests": r.successful_requests,
                    "failed_requests": r.failed_requests,
                    "success_rate": round(r.successful_requests / r.total_requests, 4) if r.total_requests > 0 else 0.0,
                    "avg_latency_ms": r.avg_latency_ms,
                    "p50_latency_ms": r.p50_latency_ms,
                    "p95_latency_ms": r.p95_latency_ms,
                    "total_prompt_tokens": r.total_prompt_tokens,
                    "total_completion_tokens": r.total_completion_tokens,
                    "total_tokens": r.total_tokens,
                    "faithfulness_score": r.faithfulness_score,
                    "relevancy_score": r.relevancy_score,
                    "total_cost_usd": r.total_cost_usd,
                    "pricing_data": r.pricing_data,
                }
                for r in results
            ]
        }


provider_benchmark_engine = ProviderBenchmarkEngine()
