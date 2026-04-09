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

    catalog_ingest_enabled: bool = Field(default=False)
    google_sheets_sheet_id: str = Field(default="")
    google_sheets_tab_name: str = Field(default="Catalog")
    google_sheets_credentials_path: str = Field(default="")
    google_sheets_service_account_json: str = Field(default="")
    google_sheets_use_service_account: bool = Field(default=False)

    meilisearch_url: str = Field(default="http://localhost:7700")
    meilisearch_api_key: str = Field(default="")
    meilisearch_index: str = Field(default="compound_search")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
