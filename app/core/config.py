from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="CycleSync")
    app_env: str = Field(default="dev")
    log_level: str = Field(default="INFO")

    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    bot_token: str = Field(default="")

    postgres_dsn: str = Field(
        default="postgresql+asyncpg://cyclesync:cyclesync@localhost:5432/cyclesync"
    )
    redis_dsn: str = Field(default="redis://localhost:6379/0")

    timezone_default: str = Field(default="UTC")
    reminder_default_time_local: str = Field(default="09:00")

    catalog_ingest_enabled: bool = Field(default=False)
    google_sheets_sheet_id: str = Field(default="")
    google_sheets_tab_name: str = Field(default="Catalog")
    google_sheets_credentials_path: str = Field(default="")
    google_sheets_service_account_json: str = Field(default="")
    google_sheets_use_service_account: bool = Field(default=False)

    meilisearch_url: str = Field(default="http://localhost:7700")
    meilisearch_api_key: str = Field(default="")
    meilisearch_index: str = Field(default="compound_search")

    labs_triage_gateway_mode: str = Field(default="heuristic")
    labs_ai_provider: str = Field(default="openai")
    labs_ai_openai_api_key: str = Field(default="")
    labs_ai_base_url: str = Field(default="https://api.openai.com/v1")
    labs_ai_model: str = Field(default="gpt-4.1-mini")
    labs_ai_timeout_seconds: float = Field(default=8.0)
    labs_ai_prompt_version: str = Field(default="w6_pr3_v1")
    expert_case_allow_dev_access: bool = Field(default=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
