"""
Configuration Module
"""
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
import secrets


class Settings(BaseSettings):
    """Application settings."""
    
    # Application
    APP_NAME: str = "Clinical Decision Support System"
    APP_VERSION: str = "1.0.1"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_PREFIX: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/clinical_db"
    )
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_ECHO: bool = False
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 3600
    
    # JWT Authentication
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # OPENAI API
    OPENAI_API_KEY: str = Field(default="")
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TEMPERATURE: float = 0.1

    # RAG Settings - NEW
    ENABLE_RAG: bool = True
    PUBMED_API_EMAIL: str = Field(
        default="your-email@example.com",
        description="Email for PubMed API (required by NCBI)"
    )
    PUBMED_MAX_RESULTS: int = 10
    CHROMA_PERSIST_DIRECTORY: str = "./chroma_db"
    EMBEDDINGS_MODEL: str = "all-MiniLM-L6-v2"
    
    # Evidence Settings
    MIN_EVIDENCE_SCORE: float = 0.7
    MAX_CITATIONS_PER_DIAGNOSIS: int = 3
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_FILE: str = "logs/app.log"

    # Hugging Face
    HF_TOKEN: str = Field(default="")

    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    # Clinical Settings
    MAX_DIFFERENTIAL_DIAGNOSES: int = 5
    MIN_CONFIDENCE_THRESHOLD: float = 0.3
    
    @field_validator("SECRET_KEY")
    def validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return v
    
    @field_validator("HF_TOKEN")
    def validate_hf_token(cls, v: str) -> str:
        if not v:
            raise ValueError("HF_TOKEN is required for embeddings service")
        return v
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"


settings = Settings()