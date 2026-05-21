from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_key: str = "dev-api-key-change-me"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    # Comma-separated origins, e.g. http://192.168.1.10:5173. Ignored when cors_allow_all=true.
    cors_origins: str = ""
    cors_allow_all: bool = False
    # Allow https://<user>.github.io when hosting demo UI on GitHub Pages
    cors_github_pages: bool = False
    cors_origin_regex: str = ""

    database_url: str = "postgresql+asyncpg://underwrite:underwrite@localhost:5432/underwrite"
    redis_url: str = "redis://localhost:6379"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "underwrite-docs"
    minio_secure: bool = False

    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    max_agent_steps: int = 12
    geocoding_user_agent: str = "underwrite-agent/0.1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
