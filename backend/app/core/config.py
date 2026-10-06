from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HJ_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Hanicar Jobs"
    tagline: str = "Don't search. Hunt."
    version: str = "0.2.0"
    env: str = "development"
    log_level: str = "INFO"
    secret_key: str = "dev-only-change-me"
    copyright: str = "(c) 2026 Safwen Amaira = Born as root"

    database_url: str = (
        "postgresql+asyncpg://hanicar:hanicar@localhost:5432/hanicar_jobs"
    )
    database_url_sync: str = (
        "postgresql+psycopg2://hanicar:hanicar@localhost:5432/hanicar_jobs"
    )
    redis_url: str = "redis://localhost:6379/0"

    ai_enabled: bool = True
    llm_provider: str = "auto"  # auto | groq | gemini | pollinations | openai | ollama | mock | kaggle
    multi_user: bool = False
    cors_origins: str = "http://localhost:5173,http://localhost:80,http://localhost"

    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.3-70b-versatile"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    openai_reasoning_effort: str = "medium"
    openai_use_responses_api: bool = False
    # OpenRouter – free-tier models (sign up free at openrouter.ai)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "meta-llama/llama-3.2-3b-instruct:free"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:1b"
    ollama_auto_pull: bool = True
    pollinations_base_url: str = "https://text.pollinations.ai/openai"
    pollinations_model: str = "openai-fast"
    pollinations_api_key: str = ""
    auto_draft_enabled: bool = True
    auto_draft_min_score: float = 55.0
    auto_draft_limit: int = 6
    auto_polish_with_llm: bool = True
    auto_prepare_enabled: bool = True
    follow_up_days: int = 7
    deadline_radar_days: int = 14

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "Hanicar Jobs"
    smtp_use_tls: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
