import abc
import asyncio
import time
from typing import Any, AsyncIterator, Dict, List, Optional
from pydantic import BaseModel, Field

try:
    from backend.app.core.config import settings
    from backend.app.services.mock_llm import DeterministicMockLLM, MockLLMResponse
except ImportError:
    from app.core.config import settings
    from app.services.mock_llm import DeterministicMockLLM, MockLLMResponse


class NormalizedLLMResponse(BaseModel):
    """
    Normalized internal response structure across all LLM providers.
    Populated directly from authentic provider responses. Never estimates tokens.
    """
    provider: str
    model: str
    response: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    latency_ms: Optional[float] = None
    provider_request_id: Optional[str] = None
    finish_reason: Optional[str] = None
    status: str = "success"  # success | error
    error: Optional[str] = None

    # Operational metadata & tool calls
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    is_mock: bool = False

    # Backwards-compatible properties
    @property
    def content(self) -> str:
        return self.response

    @property
    def prompt_tokens(self) -> int:
        return self.input_tokens or 0

    @property
    def completion_tokens(self) -> int:
        return self.output_tokens or 0

    @property
    def provider_name(self) -> str:
        return self.provider

    @property
    def model_name(self) -> str:
        return self.model


# Alias for backward compatibility
LLMResponse = NormalizedLLMResponse


class LLMProviderError(Exception):
    """Classified exception from an LLM provider."""
    def __init__(
        self,
        message: str,
        provider: str,
        model: str,
        category: str = "PROVIDER_ERROR",  # AUTH, RATE_LIMIT, TIMEOUT, MODEL_ERROR, NETWORK
        is_recoverable: bool = False,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.model = model
        self.category = category
        self.is_recoverable = is_recoverable
        self.original_error = original_error


class BaseLLMProvider(abc.ABC):
    """Unified interface for all SentinelAI LLM Providers."""

    @abc.abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        simulate_tool_call: Optional[str] = None,
    ) -> NormalizedLLMResponse:
        """Generate a completion or tool invocation."""
        pass

    @abc.abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> NormalizedLLMResponse:
        """Generate structured JSON output adhering to a schema."""
        pass

    @abc.abstractmethod
    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        """Stream response tokens as an async generator."""
        pass

    @abc.abstractmethod
    def get_usage(self) -> Dict[str, Any]:
        """Return provider usage accounting."""
        pass

    @abc.abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Perform a real health check against the provider endpoint."""
        pass


def _extract_tool_name(t: Any) -> str:
    if isinstance(t, dict):
        return t.get("name") or t.get("tool_name", "")
    return getattr(t, "tool_name", getattr(t, "name", ""))


# ==============================================================================
# MOCK PROVIDER
# ==============================================================================

class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic Mock LLM conforming strictly to SentinelAI Data Integrity Policy.
    - Zero random numbers.
    - Explicitly flagged as is_mock=True.
    - Guarantees 100% reproducible baseline execution for tests and offline environments.
    """

    def __init__(self, model_name: str = "mock-sentinel-v1"):
        self.model_name = model_name
        self.provider_name = "mock"
        self.mock_engine = DeterministicMockLLM(model_name=model_name)
        self._last_usage: Dict[str, Any] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Any]] = None,
        temperature: float = 0.0,
        simulate_tool_call: Optional[str] = None,
    ) -> NormalizedLLMResponse:
        res: MockLLMResponse = self.mock_engine.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            available_tools=[_extract_tool_name(t) for t in tools] if tools else None,
            simulate_tool_call=simulate_tool_call,
        )
        self._last_usage = {
            "prompt_tokens": res.prompt_tokens,
            "completion_tokens": res.completion_tokens,
            "total_tokens": res.total_tokens,
        }
        return NormalizedLLMResponse(
            provider="mock",
            model=res.model_name,
            response=res.content,
            input_tokens=res.prompt_tokens,
            output_tokens=res.completion_tokens,
            total_tokens=res.total_tokens,
            latency_ms=res.latency_ms,
            provider_request_id=f"mock-req-{int(time.time()*1000)}",
            finish_reason="stop",
            status="success",
            error=None,
            tool_calls=res.tool_calls,
            is_mock=True,
        )

    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> NormalizedLLMResponse:
        base_res = await self.generate(prompt=prompt, system_prompt=system_prompt, temperature=temperature)
        json_output = '{"status": "verified", "decision": "ALLOW", "confidence": 1.0, "reason": "Mock deterministic structured evaluation"}'
        return NormalizedLLMResponse(
            provider="mock",
            model=self.model_name,
            response=json_output,
            input_tokens=base_res.input_tokens,
            output_tokens=len(json_output) // 4,
            total_tokens=(base_res.input_tokens or 0) + (len(json_output) // 4),
            latency_ms=base_res.latency_ms,
            provider_request_id=f"mock-json-{int(time.time()*1000)}",
            finish_reason="stop",
            status="success",
            error=None,
            is_mock=True,
        )

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        res = await self.generate(prompt=prompt, system_prompt=system_prompt, temperature=temperature)
        words = res.response.split(" ")
        for word in words:
            yield word + " "
            await asyncio.sleep(0.01)

    def get_usage(self) -> Dict[str, Any]:
        return dict(self._last_usage)

    async def health_check(self) -> Dict[str, Any]:
        return {
            "provider": "mock",
            "model": self.model_name,
            "connected": True,
            "status": "HEALTHY",
            "latency_ms": 0.5,
            "message": "Deterministic SentinelAI Mock Provider operational",
            "timestamp": time.time(),
        }


# ==============================================================================
# GOOGLE GEMINI PROVIDER
# ==============================================================================

class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini Provider using official Google Gen AI SDK.
    Directly extracts actual usage metadata and token counts from responses.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key if api_key is not None else settings.effective_gemini_api_key
        self.model_name = model_name or settings.GEMINI_MODEL
        self.provider_name = "gemini"
        self._last_usage: Dict[str, Any] = {}

    def _get_client(self):
        if not self.api_key:
            raise LLMProviderError(
                message="Google Gemini API key not configured. Set GEMINI_API_KEY in .env.",
                provider="gemini",
                model=self.model_name,
                category="AUTH",
                is_recoverable=False,
            )
        try:
            from google import genai
            return genai.Client(api_key=self.api_key)
        except Exception as e:
            raise LLMProviderError(
                message=f"Failed to initialize Google Gen AI Client: {str(e)}",
                provider="gemini",
                model=self.model_name,
                category="MODEL_ERROR",
                is_recoverable=False,
                original_error=e,
            )

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        simulate_tool_call: Optional[str] = None,
    ) -> NormalizedLLMResponse:
        client = self._get_client()
        from google.genai import types

        config_kwargs: Dict[str, Any] = {
            "temperature": temperature,
        }
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt

        start_time = time.perf_counter()
        try:
            resp = await client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(**config_kwargs),
            )
        except Exception as e:
            err_str = str(e).lower()
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            category = "NETWORK"
            is_rec = True
            if "api_key" in err_str or "unauthorized" in err_str or "401" in err_str or "403" in err_str:
                category = "AUTH"
                is_rec = False
            elif "rate limit" in err_str or "quota" in err_str or "429" in err_str:
                category = "RATE_LIMIT"
                is_rec = True
            elif "timeout" in err_str or "deadline" in err_str:
                category = "TIMEOUT"
                is_rec = True

            raise LLMProviderError(
                message=f"Gemini generation error: {str(e)}",
                provider="gemini",
                model=self.model_name,
                category=category,
                is_recoverable=is_rec,
                original_error=e,
            )

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Extract authentic usage metrics
        input_tokens = None
        output_tokens = None
        total_tokens = None
        if hasattr(resp, "usage_metadata") and resp.usage_metadata is not None:
            input_tokens = getattr(resp.usage_metadata, "prompt_token_count", None)
            output_tokens = getattr(resp.usage_metadata, "candidates_token_count", None)
            total_tokens = getattr(resp.usage_metadata, "total_token_count", None)

        self._last_usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }

        # Finish reason
        finish_reason = None
        if hasattr(resp, "candidates") and resp.candidates:
            finish_reason = getattr(resp.candidates[0], "finish_reason", None)
            if finish_reason is not None:
                finish_reason = str(finish_reason)

        content = resp.text or ""
        provider_req_id = getattr(resp, "response_id", None)

        # Extract tool calls if present
        tool_calls: List[Dict[str, Any]] = []
        if hasattr(resp, "function_calls") and resp.function_calls:
            for idx, fc in enumerate(resp.function_calls):
                tool_calls.append({
                    "id": f"gemini_call_{idx}",
                    "name": getattr(fc, "name", "unknown_tool"),
                    "arguments": getattr(fc, "args", {}),
                })

        return NormalizedLLMResponse(
            provider="gemini",
            model=self.model_name,
            response=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            provider_request_id=provider_req_id,
            finish_reason=finish_reason,
            status="success",
            error=None,
            tool_calls=tool_calls,
            is_mock=False,
        )

    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> NormalizedLLMResponse:
        client = self._get_client()
        from google.genai import types

        config_kwargs: Dict[str, Any] = {
            "temperature": temperature,
            "response_mime_type": "application/json",
        }
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt

        start_time = time.perf_counter()
        try:
            resp = await client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(**config_kwargs),
            )
        except Exception as e:
            raise LLMProviderError(
                message=f"Gemini structured output error: {str(e)}",
                provider="gemini",
                model=self.model_name,
                category="MODEL_ERROR",
                is_recoverable=True,
                original_error=e,
            )

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        input_tokens = getattr(resp.usage_metadata, "prompt_token_count", None) if hasattr(resp, "usage_metadata") else None
        output_tokens = getattr(resp.usage_metadata, "candidates_token_count", None) if hasattr(resp, "usage_metadata") else None
        total_tokens = getattr(resp.usage_metadata, "total_token_count", None) if hasattr(resp, "usage_metadata") else None

        return NormalizedLLMResponse(
            provider="gemini",
            model=self.model_name,
            response=resp.text or "{}",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            provider_request_id=getattr(resp, "response_id", None),
            finish_reason="stop",
            status="success",
            is_mock=False,
        )

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        client = self._get_client()
        from google.genai import types

        config_kwargs: Dict[str, Any] = {"temperature": temperature}
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt

        response_stream = await client.aio.models.generate_content_stream(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(**config_kwargs),
        )
        async for chunk in response_stream:
            if chunk.text:
                yield chunk.text

    def get_usage(self) -> Dict[str, Any]:
        return dict(self._last_usage)

    async def health_check(self) -> Dict[str, Any]:
        if not self.api_key:
            return {
                "provider": "gemini",
                "model": self.model_name,
                "connected": False,
                "status": "NOT_CONFIGURED",
                "latency_ms": None,
                "message": "GEMINI_API_KEY is not configured",
                "timestamp": time.time(),
            }

        start = time.perf_counter()
        try:
            client = self._get_client()
            # Test model availability with minimal query
            models_pager = await asyncio.wait_for(
                client.aio.models.list(config={"page_size": 1}),
                timeout=5.0
            )
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return {
                "provider": "gemini",
                "model": self.model_name,
                "connected": True,
                "status": "HEALTHY",
                "latency_ms": latency_ms,
                "message": "Connected to Google Gemini API",
                "timestamp": time.time(),
            }
        except asyncio.TimeoutError:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return {
                "provider": "gemini",
                "model": self.model_name,
                "connected": False,
                "status": "UNREACHABLE",
                "latency_ms": latency_ms,
                "message": "Gemini connection timed out (5s limit)",
                "timestamp": time.time(),
            }
        except Exception as e:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            err_msg = str(e)
            return {
                "provider": "gemini",
                "model": self.model_name,
                "connected": False,
                "status": "UNREACHABLE",
                "latency_ms": latency_ms,
                "message": f"Gemini connection failed: {err_msg[:120]}",
                "timestamp": time.time(),
            }


# ==============================================================================
# GROQ PROVIDER
# ==============================================================================

class GroqProvider(BaseLLMProvider):
    """
    Groq LLM Provider using official Groq SDK.
    Extracts authentic token metrics and request IDs directly from responses.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key if api_key is not None else settings.GROQ_API_KEY
        self.model_name = model_name or settings.GROQ_MODEL
        self.provider_name = "groq"
        self._last_usage: Dict[str, Any] = {}

    def _get_client(self):
        if not self.api_key:
            raise LLMProviderError(
                message="Groq API key not configured. Set GROQ_API_KEY in .env.",
                provider="groq",
                model=self.model_name,
                category="AUTH",
                is_recoverable=False,
            )
        try:
            from groq import AsyncGroq
            return AsyncGroq(api_key=self.api_key)
        except Exception as e:
            raise LLMProviderError(
                message=f"Failed to initialize Groq Client: {str(e)}",
                provider="groq",
                model=self.model_name,
                category="MODEL_ERROR",
                is_recoverable=False,
                original_error=e,
            )

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        simulate_tool_call: Optional[str] = None,
    ) -> NormalizedLLMResponse:
        client = self._get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: Dict[str, Any] = {
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
            kwargs["tools"] = formatted_tools

        start_time = time.perf_counter()
        try:
            resp = await client.chat.completions.create(**kwargs)
        except Exception as e:
            err_str = str(e).lower()
            category = "NETWORK"
            is_rec = True
            if "api_key" in err_str or "unauthorized" in err_str or "401" in err_str or "403" in err_str:
                category = "AUTH"
                is_rec = False
            elif "rate limit" in err_str or "429" in err_str:
                category = "RATE_LIMIT"
                is_rec = True
            elif "timeout" in err_str:
                category = "TIMEOUT"
                is_rec = True

            raise LLMProviderError(
                message=f"Groq API error: {str(e)}",
                provider="groq",
                model=self.model_name,
                category=category,
                is_recoverable=is_rec,
                original_error=e,
            )

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        input_tokens = None
        output_tokens = None
        total_tokens = None
        if hasattr(resp, "usage") and resp.usage is not None:
            input_tokens = getattr(resp.usage, "prompt_tokens", None)
            output_tokens = getattr(resp.usage, "completion_tokens", None)
            total_tokens = getattr(resp.usage, "total_tokens", None)

        self._last_usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }

        choice = resp.choices[0] if resp.choices else None
        content = choice.message.content or "" if choice and choice.message else ""
        finish_reason = getattr(choice, "finish_reason", "stop") if choice else None
        req_id = getattr(resp, "id", None)

        tool_calls: List[Dict[str, Any]] = []
        if choice and choice.message and choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                func = getattr(tc, "function", None)
                if func:
                    tool_calls.append({
                        "id": getattr(tc, "id", ""),
                        "name": getattr(func, "name", ""),
                        "arguments": getattr(func, "arguments", ""),
                    })

        return NormalizedLLMResponse(
            provider="groq",
            model=self.model_name,
            response=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            provider_request_id=req_id,
            finish_reason=finish_reason,
            status="success",
            error=None,
            tool_calls=tool_calls,
            is_mock=False,
        )

    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> NormalizedLLMResponse:
        client = self._get_client()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        start_time = time.perf_counter()
        try:
            resp = await client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            raise LLMProviderError(
                message=f"Groq structured generation error: {str(e)}",
                provider="groq",
                model=self.model_name,
                category="MODEL_ERROR",
                is_recoverable=True,
                original_error=e,
            )

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        input_tokens = getattr(resp.usage, "prompt_tokens", None) if hasattr(resp, "usage") else None
        output_tokens = getattr(resp.usage, "completion_tokens", None) if hasattr(resp, "usage") else None
        total_tokens = getattr(resp.usage, "total_tokens", None) if hasattr(resp, "usage") else None

        choice = resp.choices[0] if resp.choices else None
        content = choice.message.content or "{}" if choice and choice.message else "{}"

        return NormalizedLLMResponse(
            provider="groq",
            model=self.model_name,
            response=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            provider_request_id=getattr(resp, "id", None),
            finish_reason="stop",
            status="success",
            is_mock=False,
        )

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        client = self._get_client()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        stream_resp = await client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream_resp:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content

    def get_usage(self) -> Dict[str, Any]:
        return dict(self._last_usage)

    async def health_check(self) -> Dict[str, Any]:
        if not self.api_key:
            return {
                "provider": "groq",
                "model": self.model_name,
                "connected": False,
                "status": "NOT_CONFIGURED",
                "latency_ms": None,
                "message": "GROQ_API_KEY is not configured",
                "timestamp": time.time(),
            }

        start = time.perf_counter()
        try:
            client = self._get_client()
            models = await asyncio.wait_for(client.models.list(), timeout=5.0)
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return {
                "provider": "groq",
                "model": self.model_name,
                "connected": True,
                "status": "HEALTHY",
                "latency_ms": latency_ms,
                "message": "Connected to Groq API",
                "timestamp": time.time(),
            }
        except asyncio.TimeoutError:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return {
                "provider": "groq",
                "model": self.model_name,
                "connected": False,
                "status": "UNREACHABLE",
                "latency_ms": latency_ms,
                "message": "Groq connection timed out (5s limit)",
                "timestamp": time.time(),
            }
        except Exception as e:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return {
                "provider": "groq",
                "model": self.model_name,
                "connected": False,
                "status": "UNREACHABLE",
                "latency_ms": latency_ms,
                "message": f"Groq connection failed: {str(e)[:120]}",
                "timestamp": time.time(),
            }


# ==============================================================================
# OPENAI PROVIDER
# ==============================================================================

class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI LLM Provider using official OpenAI SDK.
    Extracts authentic token metrics and request IDs directly from responses.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key if api_key is not None else settings.OPENAI_API_KEY
        self.model_name = model_name or settings.OPENAI_MODEL
        self.provider_name = "openai"
        self._last_usage: Dict[str, Any] = {}

    def _get_client(self):
        if not self.api_key:
            raise LLMProviderError(
                message="OpenAI API key not configured. Set OPENAI_API_KEY in .env.",
                provider="openai",
                model=self.model_name,
                category="AUTH",
                is_recoverable=False,
            )
        try:
            from openai import AsyncOpenAI
            return AsyncOpenAI(api_key=self.api_key)
        except Exception as e:
            raise LLMProviderError(
                message=f"Failed to initialize OpenAI Client: {str(e)}",
                provider="openai",
                model=self.model_name,
                category="MODEL_ERROR",
                is_recoverable=False,
                original_error=e,
            )

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        simulate_tool_call: Optional[str] = None,
    ) -> NormalizedLLMResponse:
        client = self._get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: Dict[str, Any] = {
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
            kwargs["tools"] = formatted_tools

        start_time = time.perf_counter()
        try:
            resp = await client.chat.completions.create(**kwargs)
        except Exception as e:
            err_str = str(e).lower()
            category = "NETWORK"
            is_rec = True
            if "api_key" in err_str or "unauthorized" in err_str or "401" in err_str or "403" in err_str:
                category = "AUTH"
                is_rec = False
            elif "rate limit" in err_str or "429" in err_str:
                category = "RATE_LIMIT"
                is_rec = True
            elif "timeout" in err_str:
                category = "TIMEOUT"
                is_rec = True

            raise LLMProviderError(
                message=f"OpenAI API error: {str(e)}",
                provider="openai",
                model=self.model_name,
                category=category,
                is_recoverable=is_rec,
                original_error=e,
            )

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        input_tokens = None
        output_tokens = None
        total_tokens = None
        if hasattr(resp, "usage") and resp.usage is not None:
            input_tokens = getattr(resp.usage, "prompt_tokens", None)
            output_tokens = getattr(resp.usage, "completion_tokens", None)
            total_tokens = getattr(resp.usage, "total_tokens", None)

        self._last_usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }

        choice = resp.choices[0] if resp.choices else None
        content = choice.message.content or "" if choice and choice.message else ""
        finish_reason = getattr(choice, "finish_reason", "stop") if choice else None
        req_id = getattr(resp, "id", None)

        tool_calls: List[Dict[str, Any]] = []
        if choice and choice.message and choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                func = getattr(tc, "function", None)
                if func:
                    tool_calls.append({
                        "id": getattr(tc, "id", ""),
                        "name": getattr(func, "name", ""),
                        "arguments": getattr(func, "arguments", ""),
                    })

        return NormalizedLLMResponse(
            provider="openai",
            model=self.model_name,
            response=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            provider_request_id=req_id,
            finish_reason=finish_reason,
            status="success",
            error=None,
            tool_calls=tool_calls,
            is_mock=False,
        )

    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> NormalizedLLMResponse:
        client = self._get_client()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        start_time = time.perf_counter()
        try:
            resp = await client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            raise LLMProviderError(
                message=f"OpenAI structured output error: {str(e)}",
                provider="openai",
                model=self.model_name,
                category="MODEL_ERROR",
                is_recoverable=True,
                original_error=e,
            )

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        input_tokens = getattr(resp.usage, "prompt_tokens", None) if hasattr(resp, "usage") else None
        output_tokens = getattr(resp.usage, "completion_tokens", None) if hasattr(resp, "usage") else None
        total_tokens = getattr(resp.usage, "total_tokens", None) if hasattr(resp, "usage") else None

        choice = resp.choices[0] if resp.choices else None
        content = choice.message.content or "{}" if choice and choice.message else "{}"

        return NormalizedLLMResponse(
            provider="openai",
            model=self.model_name,
            response=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            provider_request_id=getattr(resp, "id", None),
            finish_reason="stop",
            status="success",
            is_mock=False,
        )

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        client = self._get_client()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        stream_resp = await client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream_resp:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content

    def get_usage(self) -> Dict[str, Any]:
        return dict(self._last_usage)

    async def health_check(self) -> Dict[str, Any]:
        if not self.api_key:
            return {
                "provider": "openai",
                "model": self.model_name,
                "connected": False,
                "status": "NOT_CONFIGURED",
                "latency_ms": None,
                "message": "OPENAI_API_KEY is not configured",
                "timestamp": time.time(),
            }

        start = time.perf_counter()
        try:
            client = self._get_client()
            models = await asyncio.wait_for(client.models.list(), timeout=5.0)
            latency_ms = round((time.perf_counter() - start) * 1000, 2)

            # Probe completion to verify quota availability
            try:
                await asyncio.wait_for(
                    client.chat.completions.create(
                        model=self.model_name,
                        messages=[{"role": "user", "content": "ping"}],
                        max_tokens=1,
                    ),
                    timeout=4.0,
                )
                return {
                    "provider": "openai",
                    "model": self.model_name,
                    "connected": True,
                    "status": "HEALTHY",
                    "latency_ms": latency_ms,
                    "message": "Connected to OpenAI API (Active & Funded)",
                    "timestamp": time.time(),
                }
            except Exception as gen_err:
                gen_msg = str(gen_err).lower()
                if "quota" in gen_msg or "rate limit" in gen_msg or "429" in gen_msg or "credits" in gen_msg:
                    return {
                        "provider": "openai",
                        "model": self.model_name,
                        "connected": False,
                        "status": "QUOTA_EXHAUSTED",
                        "latency_ms": latency_ms,
                        "message": "OpenAI API key authenticated, but billing quota is exhausted ($0 balance). Fallback routing active.",
                        "timestamp": time.time(),
                    }
                return {
                    "provider": "openai",
                    "model": self.model_name,
                    "connected": True,
                    "status": "HEALTHY",
                    "latency_ms": latency_ms,
                    "message": f"Connected to OpenAI API ({str(gen_err)[:80]})",
                    "timestamp": time.time(),
                }
        except asyncio.TimeoutError:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return {
                "provider": "openai",
                "model": self.model_name,
                "connected": False,
                "status": "UNREACHABLE",
                "latency_ms": latency_ms,
                "message": "OpenAI connection timed out (5s limit)",
                "timestamp": time.time(),
            }
        except Exception as e:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return {
                "provider": "openai",
                "model": self.model_name,
                "connected": False,
                "status": "UNREACHABLE",
                "latency_ms": latency_ms,
                "message": f"OpenAI connection failed: {str(e)[:120]}",
                "timestamp": time.time(),
            }


# ==============================================================================
# PROVIDER FACTORY
# ==============================================================================

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

    if prov == "gemini":
        key = api_key if api_key is not None else settings.effective_gemini_api_key
        return GeminiProvider(api_key=key, model_name=model_name or settings.GEMINI_MODEL)

    if prov == "groq":
        key = api_key if api_key is not None else settings.GROQ_API_KEY
        return GroqProvider(api_key=key, model_name=model_name or settings.GROQ_MODEL)

    if prov == "openai":
        key = api_key if api_key is not None else settings.OPENAI_API_KEY
        return OpenAIProvider(api_key=key, model_name=model_name or settings.OPENAI_MODEL)

    return MockLLMProvider(model_name=model_name or settings.DEFAULT_LLM_MODEL)
