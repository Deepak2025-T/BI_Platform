from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "change-me-to-a-long-random-string"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://bi:bi_dev_password@localhost:5432/bi_db"
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_expire_minutes: int = 480
    cors_origins: str = "http://localhost:5173"
    # Fernet key that encrypts saved database passwords and AI API keys. Back it up separately:
    # without it, they can't be read.
    connections_key: str = ""
    # How long to wait for an AI model to answer. Big local models on a CPU load slowly on the
    # first call, so this allows for that; lower it if you'd rather fail fast.
    ai_timeout_seconds: int = 300
    # How long Ollama keeps a model in memory after a call, so later calls skip the load time.
    ollama_keep_alive: str = "30m"
    # Runs scheduled report refreshes inside the API process.
    scheduler_enabled: bool = True

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


    def setup_warnings(self) -> list[str]:
        """Configuration problems a manager should fix, shown on the Settings page."""
        warnings = []
        if self.jwt_secret == DEFAULT_JWT_SECRET or len(self.jwt_secret) < 32:
            warnings.append("JWT_SECRET in backend/.env is still the default or too short. Set a long random value.")
        if not self.connections_key:
            warnings.append("CONNECTIONS_KEY is not set in backend/.env, so database connections and AI API keys can't be saved.")
        return warnings


settings = Settings()
