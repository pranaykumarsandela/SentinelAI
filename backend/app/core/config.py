from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """SentinelAI System Configuration Settings."""
    
    # Application
    PROJECT_NAME: str = "SentinelAI"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000"
    ]

    # Database
    # Default to async SQLite for local execution; can be switched to PostgreSQL
    DATABASE_URL: str = "sqlite+aiosqlite:///./sentinelai.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    JWT_SECRET_KEY: str = "sentinelai-secret-key-change-in-production"
    
    # LLM Settings
    DEFAULT_LLM_PROVIDER: str = "mock"  # "mock", "gemini", "groq", "openai"
    DEFAULT_LLM_MODEL: str = "mock-sentinel-v1"
    
    GEMINI_API_KEY: str | None = None
    GOOGLE_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "qwen/qwen3.8-27b"
    
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    # Qdrant
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_IN_MEMORY: bool = True
    
    # Observability (Langfuse)
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_BASE_URL: str | None = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    LANGFUSE_ENABLED: bool = True
    LANGFUSE_TIMEOUT: float = 5.0
    LANGFUSE_CAPTURE_INPUT_OUTPUT: bool = True
    ENABLE_STRUCTURED_LOGGING: bool = True

    @property
    def effective_gemini_api_key(self) -> str | None:
        """Returns the canonical Gemini API key (GEMINI_API_KEY or GOOGLE_API_KEY)."""
        return self.GEMINI_API_KEY or self.GOOGLE_API_KEY

    @property
    def effective_langfuse_host(self) -> str:
        """Returns the canonical Langfuse endpoint URL (LANGFUSE_BASE_URL takes precedence)."""
        url = (self.LANGFUSE_BASE_URL or self.LANGFUSE_HOST or "https://cloud.langfuse.com").strip().rstrip("/")
        return url

    @property
    def is_langfuse_configured(self) -> bool:
        """Checks whether Langfuse is enabled and has valid API keys configured."""
        return bool(self.LANGFUSE_ENABLED and self.LANGFUSE_PUBLIC_KEY and self.LANGFUSE_SECRET_KEY)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

