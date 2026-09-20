from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ReviewerConfig(BaseModel):
    username: str
    github_id: int | None = None


class ActionConfig(BaseModel):
    action: Literal["approve", "request_review", "create_check", "noop"]
    reviewers: list[str] = Field(default_factory=list)
    codeowners_only: bool = False
    check_name: str | None = None


class RoutingConfig(BaseModel):
    reviewers: list[ReviewerConfig] = Field(default_factory=list)
    actions: dict[str, ActionConfig] = Field(default_factory=dict)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    env: str = "development"
    log_level: str = "INFO"
    config_path: Path = Path("review-routing.yml")
    database_url: str = "postgresql+psycopg://jevpr:jevpr@localhost:5432/jevpr"
    redis_url: str = "redis://localhost:6379/0"
    github_app_id: int | None = None
    github_app_private_key: str | None = None
    github_webhook_secret: str | None = None
    typesafe_api_key: str | None = None

    def load_routing_config(self) -> RoutingConfig:
        config_path = self.config_path
        if not config_path.is_absolute():
            config_path = Path.cwd() / config_path

        if not config_path.exists():
            return RoutingConfig()

        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        return RoutingConfig.model_validate(data)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()