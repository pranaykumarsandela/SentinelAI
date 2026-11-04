import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

try:
    from backend.app.core.config import settings
except ImportError:
    from app.core.config import settings


# ==============================================================================
# VERSIONED PRICING CATALOG
# ==============================================================================

PRICING_CATALOG_V1: Dict[str, Any] = {
    "source": "Official Published Cloud Provider Rates",
    "version": "2026.03.01",
    "last_updated": "2026-03-01T00:00:00Z",
    "models": {
        "gemini-2.5-flash": {
            "input_per_million": 0.075,
            "output_per_million": 0.30,
        },
        "gemini-2.5-pro": {
            "input_per_million": 1.25,
            "output_per_million": 5.00,
        },
        "gemini-1.5-flash": {
            "input_per_million": 0.075,
            "output_per_million": 0.30,
        },
        "gemini-1.5-pro": {
            "input_per_million": 1.25,
            "output_per_million": 5.00,
        },
        "llama-3.3-70b-versatile": {
            "input_per_million": 0.59,
            "output_per_million": 0.79,
        },
        "llama-3.1-8b-instant": {
            "input_per_million": 0.05,
            "output_per_million": 0.08,
        },
        "mixtral-8x7b-32768": {
            "input_per_million": 0.24,
            "output_per_million": 0.24,
        },
        "gpt-4o-mini": {
            "input_per_million": 0.15,
            "output_per_million": 0.60,
        },
        "gpt-4o": {
            "input_per_million": 2.50,
            "output_per_million": 10.00,
        },
        "gpt-4-turbo": {
            "input_per_million": 10.00,
            "output_per_million": 30.00,
        },
        "mock-sentinel-v1": {
            "input_per_million": 0.0,
            "output_per_million": 0.0,
        },
        "mock-sentinel-pro": {
            "input_per_million": 0.0,
            "output_per_million": 0.0,
        },
    }
}


# ==============================================================================
# SUPPORTED MODEL ALLOWLIST & CAPABILITY SPECIFICATIONS
# ==============================================================================

SUPPORTED_MODELS_ALLOWLIST: Dict[str, Dict[str, Any]] = {
    "gemini": {
        "gemini-2.5-flash": {
            "display_name": "Google Gemini 2.5 Flash",
            "context_window": 1048576,
            "supports_streaming": True,
            "supports_tool_calling": True,
            "supports_structured_output": True,
            "supports_json_mode": True,
            "is_default": True,
        },
        "gemini-2.5-pro": {
            "display_name": "Google Gemini 2.5 Pro",
            "context_window": 2097152,
            "supports_streaming": True,
            "supports_tool_calling": True,
            "supports_structured_output": True,
            "supports_json_mode": True,
            "is_default": False,
        },
        "gemini-1.5-flash": {
            "display_name": "Google Gemini 1.5 Flash",
            "context_window": 1048576,
            "supports_streaming": True,
            "supports_tool_calling": True,
            "supports_structured_output": True,
            "supports_json_mode": True,
            "is_default": False,
        },
        "gemini-1.5-pro": {
            "display_name": "Google Gemini 1.5 Pro",
            "context_window": 2097152,
            "supports_streaming": True,
            "supports_tool_calling": True,
            "supports_structured_output": True,
            "supports_json_mode": True,
            "is_default": False,
        },
    },
    "groq": {
        "llama-3.3-70b-versatile": {
            "display_name": "Llama 3.3 70B Versatile",
            "context_window": 128000,
            "supports_streaming": True,
            "supports_tool_calling": True,
            "supports_structured_output": True,
            "supports_json_mode": True,
            "is_default": True,
        },
        "llama-3.1-8b-instant": {
            "display_name": "Llama 3.1 8B Instant",
            "context_window": 128000,
            "supports_streaming": True,
            "supports_tool_calling": True,
            "supports_structured_output": True,
            "supports_json_mode": True,
            "is_default": False,
        },
        "mixtral-8x7b-32768": {
            "display_name": "Mixtral 8x7B (32k Context)",
            "context_window": 32768,
            "supports_streaming": True,
            "supports_tool_calling": True,
            "supports_structured_output": True,
            "supports_json_mode": True,
            "is_default": False,
        },
    },
    "openai": {
        "gpt-4o-mini": {
            "display_name": "OpenAI GPT-4o Mini",
            "context_window": 128000,
            "supports_streaming": True,
            "supports_tool_calling": True,
            "supports_structured_output": True,
            "supports_json_mode": True,
            "is_default": True,
        },
        "gpt-4o": {
            "display_name": "OpenAI GPT-4o",
            "context_window": 128000,
            "supports_streaming": True,
            "supports_tool_calling": True,
            "supports_structured_output": True,
            "supports_json_mode": True,
            "is_default": False,
        },
        "gpt-4-turbo": {
            "display_name": "OpenAI GPT-4 Turbo",
            "context_window": 128000,
            "supports_streaming": True,
            "supports_tool_calling": True,
            "supports_structured_output": True,
            "supports_json_mode": True,
            "is_default": False,
        },
    },
    "mock": {
        "mock-sentinel-v1": {
            "display_name": "SentinelAI Mock Engine v1 (Deterministic)",
            "context_window": 32768,
            "supports_streaming": True,
            "supports_tool_calling": True,
            "supports_structured_output": True,
            "supports_json_mode": True,
            "is_default": True,
        },
        "mock-sentinel-pro": {
            "display_name": "SentinelAI Mock Engine Pro (Deterministic)",
            "context_window": 65536,
            "supports_streaming": True,
            "supports_tool_calling": True,
            "supports_structured_output": True,
            "supports_json_mode": True,
            "is_default": False,
        },
    },
}


class TaskRouteItem(BaseModel):
    provider: str
    model: str


class FallbackRouteItem(BaseModel):
    provider: str
    model: str


class ModelRouterConfiguration(BaseModel):
    default_provider: str = Field(default="mock")
    default_model: str = Field(default="mock-sentinel-v1")
    task_routing: Dict[str, TaskRouteItem] = Field(default_factory=lambda: {
        "planning": TaskRouteItem(provider="mock", model="mock-sentinel-v1"),
        "fast_classification": TaskRouteItem(provider="mock", model="mock-sentinel-v1"),
        "document_answering": TaskRouteItem(provider="mock", model="mock-sentinel-v1"),
        "evaluation": TaskRouteItem(provider="mock", model="mock-sentinel-v1"),
        "structured_output": TaskRouteItem(provider="mock", model="mock-sentinel-v1"),
    })
    fallback_chains: Dict[str, List[FallbackRouteItem]] = Field(default_factory=lambda: {
        "default": [
            FallbackRouteItem(provider="gemini", model="gemini-2.5-flash"),
            FallbackRouteItem(provider="groq", model="llama-3.3-70b-versatile"),
            FallbackRouteItem(provider="openai", model="gpt-4o-mini"),
            FallbackRouteItem(provider="mock", model="mock-sentinel-v1"),
        ]
    })


class ModelRouter:
    """
    Centralized model router managing allowlists, task-based routing,
    and verified cost calculations.
    """

    def __init__(self):
        # Initialize default configuration based on environment settings
        def_prov = (settings.DEFAULT_LLM_PROVIDER or "mock").lower()
        def_model = settings.DEFAULT_LLM_MODEL or "mock-sentinel-v1"
        if def_prov == "gemini":
            def_model = settings.GEMINI_MODEL
        elif def_prov == "groq":
            def_model = settings.GROQ_MODEL
        elif def_prov == "openai":
            def_model = settings.OPENAI_MODEL

        self.config = ModelRouterConfiguration(
            default_provider=def_prov,
            default_model=def_model,
            task_routing={
                "planning": TaskRouteItem(provider=def_prov, model=def_model),
                "fast_classification": TaskRouteItem(
                    provider="groq" if settings.GROQ_API_KEY else def_prov,
                    model=settings.GROQ_MODEL if settings.GROQ_API_KEY else def_model,
                ),
                "document_answering": TaskRouteItem(
                    provider="gemini" if settings.GEMINI_API_KEY else def_prov,
                    model=settings.GEMINI_MODEL if settings.GEMINI_API_KEY else def_model,
                ),
                "evaluation": TaskRouteItem(
                    provider="openai" if settings.OPENAI_API_KEY else def_prov,
                    model=settings.OPENAI_MODEL if settings.OPENAI_API_KEY else def_model,
                ),
                "structured_output": TaskRouteItem(provider=def_prov, model=def_model),
            },
            fallback_chains={
                "default": [
                    FallbackRouteItem(provider="gemini", model=settings.GEMINI_MODEL),
                    FallbackRouteItem(provider="groq", model=settings.GROQ_MODEL),
                    FallbackRouteItem(provider="openai", model=settings.OPENAI_MODEL),
                    FallbackRouteItem(provider="mock", model="mock-sentinel-v1"),
                ]
            }
        )

    def is_model_supported(self, provider: str, model_id: str) -> bool:
        """Validate model IDs against supported provider models."""
        prov_models = SUPPORTED_MODELS_ALLOWLIST.get(provider.lower())
        if not prov_models:
            return False
        return model_id in prov_models

    def validate_route(self, provider: str, model: str) -> None:
        """Raises ValueError if provider or model is invalid."""
        p_lower = provider.lower()
        if p_lower not in SUPPORTED_MODELS_ALLOWLIST:
            raise ValueError(f"Unsupported LLM provider '{provider}'. Allowed: {list(SUPPORTED_MODELS_ALLOWLIST.keys())}")
        if not self.is_model_supported(p_lower, model):
            allowed = list(SUPPORTED_MODELS_ALLOWLIST[p_lower].keys())
            raise ValueError(f"Unsupported model '{model}' for provider '{provider}'. Allowed: {allowed}")

    def get_route_for_task(self, task_type: str) -> TaskRouteItem:
        """Returns the configured route for a specific task."""
        route = self.config.task_routing.get(task_type)
        if route and self.is_model_supported(route.provider, route.model):
            return route
        return TaskRouteItem(
            provider=self.config.default_provider,
            model=self.config.default_model,
        )

    def get_fallback_chain(self, task_type: Optional[str] = None) -> List[FallbackRouteItem]:
        """Returns fallback candidates for a task or default."""
        if task_type and task_type in self.config.fallback_chains:
            return self.config.fallback_chains[task_type]
        return self.config.fallback_chains.get("default", [])

    def calculate_cost(self, model: str, input_tokens: Optional[int], output_tokens: Optional[int]) -> Optional[float]:
        """
        Calculate verified cost based strictly on PRICING_CATALOG_V1.
        Returns None (N/A) if pricing is not verified or tokens are missing.
        Never fabricates costs.
        """
        if input_tokens is None or output_tokens is None:
            return None

        pricing = PRICING_CATALOG_V1["models"].get(model)
        if not pricing:
            return None

        in_rate = pricing["input_per_million"] / 1_000_000.0
        out_rate = pricing["output_per_million"] / 1_000_000.0
        cost = (input_tokens * in_rate) + (output_tokens * out_rate)
        return round(cost, 6)

    def get_pricing_metadata(self, model: str) -> Optional[Dict[str, Any]]:
        """Returns versioned pricing metadata for auditing."""
        pricing = PRICING_CATALOG_V1["models"].get(model)
        if not pricing:
            return None
        return {
            "source": PRICING_CATALOG_V1["source"],
            "version": PRICING_CATALOG_V1["version"],
            "model": model,
            "input_per_million": pricing["input_per_million"],
            "output_per_million": pricing["output_per_million"],
            "calculation_timestamp": time.time(),
        }

    def update_configuration(
        self,
        default_provider: Optional[str] = None,
        default_model: Optional[str] = None,
        task_routing: Optional[Dict[str, Dict[str, str]]] = None,
        fallback_chains: Optional[Dict[str, List[Dict[str, str]]]] = None,
    ) -> ModelRouterConfiguration:
        """Update router configuration with rigorous validation."""
        if default_provider:
            d_prov = default_provider.lower()
            d_model = default_model or self.config.default_model
            self.validate_route(d_prov, d_model)
            self.config.default_provider = d_prov
            self.config.default_model = d_model

        if task_routing:
            for task, r in task_routing.items():
                p = r.get("provider", self.config.default_provider).lower()
                m = r.get("model", self.config.default_model)
                self.validate_route(p, m)
                self.config.task_routing[task] = TaskRouteItem(provider=p, model=m)

        if fallback_chains:
            for chain_name, chain_items in fallback_chains.items():
                validated_chain = []
                for item in chain_items:
                    p = item.get("provider", "mock").lower()
                    m = item.get("model", "mock-sentinel-v1")
                    self.validate_route(p, m)
                    validated_chain.append(FallbackRouteItem(provider=p, model=m))
                self.config.fallback_chains[chain_name] = validated_chain

        return self.config


model_router = ModelRouter()
