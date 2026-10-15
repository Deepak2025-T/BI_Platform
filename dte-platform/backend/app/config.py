"""Application settings (env-driven). LLM provider choice is stored in the DB so it can be changed from the UI."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Metadata + vector store (PostgreSQL with pgvector)
    app_db_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/dte_app"
    # Secret used to encrypt stored DB passwords / API keys (Fernet key, 32 url-safe base64 bytes)
    secret_key: str = "change-me-please-change-me-please-change-me="

    # Defaults for the model configuration screen (overridable in UI)
    default_llm_provider: str = "ollama"            # "ollama" | "claude"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder:7b"
    ollama_embed_model: str = "nomic-embed-text"
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-5"
    claude_fast_model: str = "claude-haiku-4-5"

    embedding_dim: int = 768                        # nomic-embed-text = 768
    max_rows_default: int = 5000
    statement_timeout_ms: int = 30000
    sql_max_fix_attempts: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
