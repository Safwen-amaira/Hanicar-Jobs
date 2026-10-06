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
    version: str = "0.1.0"
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

    ai_enabled: bool = False
    llm_provider: str = "mock"  # mock | openai | ollama | kaggle
    multi_user: bool = False
    cors_origins: str = "http://localhost:5173,http://localhost:80,http://localhost"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
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
