import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class MockLLMResponse(BaseModel):
    content: str
    tool_calls: List[Dict[str, Any]] = []
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    is_mock: bool = True
    model_name: str = "mock-sentinel-v1"


class DeterministicMockLLM:
    """
    Deterministic Mock LLM Engine conforming to SentinelAI Data Integrity Policy.
    - Zero random values
    - Precise deterministic token calculation based on content
    - Realistic simulation of assistant reasoning, tool calls, or refusals
    - Explicitly sets is_mock=True
    """

    def __init__(self, model_name: str = "mock-sentinel-v1"):
        self.model_name = model_name

    def _count_tokens(self, text: str) -> int:
        """Deterministic token approximation: standard 1 token per 4 characters (min 1)."""
        if not text:
            return 0
        return max(1, len(text) // 4)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        available_tools: Optional[List[str]] = None,
        simulate_tool_call: Optional[str] = None,
    ) -> MockLLMResponse:
        start_time = time.perf_counter()
        
        prompt_lower = prompt.lower()
        content = ""
        tool_calls = []

        # Deterministic response rules based on input pattern
        if simulate_tool_call:
            content = f"I will now execute the tool: {simulate_tool_call} to complete your request."
            if simulate_tool_call == "check_order_status":
                args = {"order_id": "ORD-1001"}
            elif simulate_tool_call == "request_refund":
                args = {"order_id": "ORD-1001", "amount": 45.0, "reason": "Defective item on delivery"}
            elif simulate_tool_call == "search_documents":
                args = {"query": prompt, "top_k": 3}
            elif simulate_tool_call == "retrieve_document":
                args = {"document_id": "doc_sample_001"}
            elif simulate_tool_call == "create_support_ticket":
                args = {"customer_id": "CUST-001", "issue_summary": "Order inquiry assistance needed"}
            else:
                args = {"query": prompt, "action": "execute"}

            tool_calls.append({
                "name": simulate_tool_call,
                "arguments": args,
                "id": "mock_call_001"
            })
        elif "delete" in prompt_lower or "drop" in prompt_lower or "transfer" in prompt_lower:
            content = "Attempting to execute privileged tool operation for data modification."
            tool_calls.append({
                "name": "database_admin_tool",
                "arguments": {"command": prompt},
                "id": "mock_call_crit_001"
            })
        elif "calculate" in prompt_lower or "math" in prompt_lower:
            content = "The mathematical computation evaluates to 42."
        elif "who are you" in prompt_lower or "identity" in prompt_lower:
            content = "I am SentinelAI Mock Agent, running in isolated test mode for security evaluation."
        elif "weather" in prompt_lower:
            content = "Current simulated temperature is 22 degrees Celsius with clear skies."
        elif "error" in prompt_lower:
            content = "Simulated standard execution response for diagnostic verification."
        else:
            content = (
                f"SentinelAI Mock Response: Received prompt of {len(prompt)} characters. "
                "Verified safe operational parameters in mock execution mode."
            )

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        # Add deterministic processing simulation based on token count (0.05ms per token)
        total_prompt_text = (system_prompt or "") + prompt
        p_tokens = self._count_tokens(total_prompt_text)
        c_tokens = self._count_tokens(content)
        total_tokens = p_tokens + c_tokens
        
        latency_ms = max(0.1, round(elapsed_ms + (total_tokens * 0.05), 2))

        return MockLLMResponse(
            content=content,
            tool_calls=tool_calls,
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            is_mock=True,
            model_name=self.model_name
        )


mock_llm_service = DeterministicMockLLM()

