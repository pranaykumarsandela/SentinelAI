import abc
import time
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel

try:
    from backend.app.core.config import settings
    from backend.app.services.mock_llm import DeterministicMockLLM, MockLLMResponse
except ImportError:
    from app.core.config import settings
    from app.services.mock_llm import DeterministicMockLLM, MockLLMResponse


class LLMResponse(BaseModel):
    content: str
    tool_calls: List[Dict[str, Any]] = []
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    is_mock: bool = True
    model_name: str
    provider_name: str


class BaseLLMProvider(abc.ABC):
    @abc.abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        simulate_tool_call: Optional[str] = None,
    ) -> LLMResponse:
        """Generate response or tool calls."""
        pass


def _extract_tool_name(t: Any) -> str:
    if isinstance(t, dict):
        return t.get("name") or t.get("tool_name", "")
    return getattr(t, "tool_name", getattr(t, "name", ""))


class MockLLMProvider(BaseLLMProvider):
    """Deterministic Mock LLM conforming strictly to SentinelAI Data Integrity Policy."""

    def __init__(self, model_name: str = "mock-sentinel-v1"):
        self.model_name = model_name
        self.mock_engine = DeterministicMockLLM(model_name=model_name)

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Any]] = None,
        temperature: float = 0.0,
        simulate_tool_call: Optional[str] = None,
    ) -> LLMResponse:
        res: MockLLMResponse = self.mock_engine.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            available_tools=[_extract_tool_name(t) for t in tools] if tools else None,
            simulate_tool_call=simulate_tool_call,
        )
        return LLMResponse(
            content=res.content,
            tool_calls=res.tool_calls,
            prompt_tokens=res.prompt_tokens,
            completion_tokens=res.completion_tokens,
            total_tokens=res.total_tokens,
            latency_ms=res.latency_ms,
            is_mock=True,
            model_name=res.model_name,
            provider_name="mock",
        )


class GroqProvider(BaseLLMProvider):
    """
    Groq LLM Provider.
    Extracts real token usage and latency from actual Groq API responses.
    Never fabricates metrics.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "llama-3.1-8b-instant"):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model_name = model_name
        self.endpoint = "https://api.groq.com/openai/v1/chat/completions"

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        simulate_tool_call: Optional[str] = None,
    ) -> LLMResponse:
        if not self.api_key:
            raise ValueError("Groq API key not configured. Provide GROQ_API_KEY or use MockLLMProvider.")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
        }

        if tools:
            formatted_tools = []
            for tool in tools:
                formatted_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.get("name"),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
                    }
                })
            payload["tools"] = formatted_tools

        start_time = time.perf_counter()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(self.endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        content = msg.get("content") or ""
        tool_calls_raw = msg.get("tool_calls") or []

        tool_calls = []
        for tc in tool_calls_raw:
            func = tc.get("function", {})
            tool_calls.append({
                "id": tc.get("id"),
                "name": func.get("name"),
                "arguments": func.get("arguments"),
            })

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            is_mock=False,
            model_name=self.model_name,
            provider_name="groq",
        )


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI LLM Provider.
    Extracts real token usage and latency from actual OpenAI API responses.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gpt-4o-mini"):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model_name = model_name
        self.endpoint = "https://api.openai.com/v1/chat/completions"

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        simulate_tool_call: Optional[str] = None,
    ) -> LLMResponse:
        if not self.api_key:
            raise ValueError("OpenAI API key not configured. Provide OPENAI_API_KEY or use MockLLMProvider.")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
        }

        if tools:
            formatted_tools = []
            for tool in tools:
                formatted_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.get("name"),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
                    }
                })
            payload["tools"] = formatted_tools

        start_time = time.perf_counter()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(self.endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        content = msg.get("content") or ""
        tool_calls_raw = msg.get("tool_calls") or []

        tool_calls = []
        for tc in tool_calls_raw:
            func = tc.get("function", {})
            tool_calls.append({
                "id": tc.get("id"),
                "name": func.get("name"),
                "arguments": func.get("arguments"),
            })

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            is_mock=False,
            model_name=self.model_name,
            provider_name="openai",
        )


def get_llm_provider(
    provider_name: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    is_mock: Optional[bool] = None,
) -> BaseLLMProvider:
    """
    Factory creating LLM provider.
    Defaults to MockLLMProvider if is_mock is True, provider is 'mock', or no keys exist.
    """
    prov = (provider_name or settings.DEFAULT_LLM_PROVIDER).lower()
    
    if is_mock is True or prov == "mock":
        return MockLLMProvider(model_name=model_name or settings.DEFAULT_LLM_MODEL)
    
    if prov == "groq":
        key = api_key or settings.GROQ_API_KEY
        if key:
            return GroqProvider(api_key=key, model_name=model_name or "llama-3.1-8b-instant")
        return MockLLMProvider(model_name=model_name or "mock-groq-fallback")
    
    if prov == "openai":
        key = api_key or settings.OPENAI_API_KEY
        if key:
            return OpenAIProvider(api_key=key, model_name=model_name or "gpt-4o-mini")
        return MockLLMProvider(model_name=model_name or "mock-openai-fallback")

    return MockLLMProvider(model_name=model_name or settings.DEFAULT_LLM_MODEL)
