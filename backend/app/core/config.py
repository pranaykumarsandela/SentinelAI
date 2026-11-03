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
    
    # LLM Settings
    DEFAULT_LLM_PROVIDER: str = "mock"  # "mock", "groq", "openai"
    DEFAULT_LLM_MODEL: str = "mock-sentinel-v1"
    GROQ_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    
    # Qdrant
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_IN_MEMORY: bool = True
    
    # Observability
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    ENABLE_STRUCTURED_LOGGING: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
