from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://margamitra:margamitra@localhost:5432/margamitra"
    llm_provider: str = "none"
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = "claude-haiku-5-5"
    vision_model: str = "claude-sonnet-5-5"
    copilot_model: str = "claude-sonnet-5-5"
    llm_cache: bool = True
    weather_mode: Literal["fixture", "live"] = "fixture"
    scenario_seed: int = 1
    cors_origins: str = "http://localhost:5173"
    public_base_url: str = "http://localhost:8000"
    uploads_dir: str = "uploads"
    today_day: int = 8

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
