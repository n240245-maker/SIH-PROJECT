"""Environment and path configuration for the local application."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from intelligence.data.paths import ProjectPaths


class AppSettings(BaseSettings):
    app_name: str = "MPLADS Sentinel"
    api_prefix: str = "/api/v1"
    as_of_date: str = "2026-09-01"
    cors_origins: str = "http://localhost:3000"
    environment: str = "development"
    runtime_data_dir: Path | None = None

    model_config = SettingsConfigDict(
        env_prefix="MPLADS_", env_file_encoding="utf-8", extra="ignore"
    )

    @field_validator("cors_origins")
    @classmethod
    def reject_wildcard(cls, value: str) -> str:
        if "*" in {part.strip() for part in value.split(",")}:
            raise ValueError("Wildcard CORS origins are not allowed")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [part.strip() for part in self.cors_origins.split(",") if part.strip()]


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    paths = ProjectPaths.discover()
    settings = AppSettings(_env_file=paths.project_root / ".env")
    if settings.runtime_data_dir is None:
        settings.runtime_data_dir = paths.project_root / "data" / "runtime"
    else:
        settings.runtime_data_dir = settings.runtime_data_dir.expanduser().resolve()
    return settings
