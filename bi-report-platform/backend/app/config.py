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
    # A dashboard is many model calls (an outline, then one per chart), so it gets its own budget.
    # When it runs out, the charts already built are kept and the rest are reported as failed.
    ai_dashboard_budget_seconds: int = 900
    # How many charts are written at once. Ollama queues what it can't run in parallel, so raising
    # this helps a hosted model far more than a local one.
    ai_max_parallel: int = 4
    # Room for one Ollama call: the prompt and the answer together, in tokens. Ollama's own
    # default is 4096 whatever the model supports, which a dozen tables of schema will fill.
    # More costs memory; less cuts answers short.
    ollama_num_ctx: int = 16384
    # How much of that window the table descriptions may take. A connection can share far more
    # tables than any model's context holds - 164 OpenPages object types come to about 33,000
    # tokens - and a context that overflows is truncated silently, so the model ends up insisting
    # that real tables don't exist. Past this budget the most relevant tables are described and
    # the rest are listed by name.
    ai_schema_budget_tokens: int = 6000
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
