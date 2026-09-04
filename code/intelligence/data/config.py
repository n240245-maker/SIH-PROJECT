"""Environment-backed Day-1 settings."""

from __future__ import annotations

from datetime import date

from pydantic_settings import BaseSettings, SettingsConfigDict

from .paths import ProjectPaths


CONTROLLED_PROTOTYPE_AS_OF_DATE = date(2026, 9, 1)


class Day1Settings(BaseSettings):
    """Small configuration surface for deterministic data validation."""

    environment: str = "development"
    as_of_date: date = CONTROLLED_PROTOTYPE_AS_OF_DATE

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
        env_prefix="",
    )


def load_settings(
    paths: ProjectPaths | None = None,
    *,
    as_of_date: date | str | None = None,
) -> Day1Settings:
    """Load settings from process environment and an optional uncommitted root .env file."""

    resolved_paths = paths or ProjectPaths.discover()
    values: dict[str, date | str] = {}
    if as_of_date is not None:
        values["as_of_date"] = as_of_date
    return Day1Settings(
        _env_file=resolved_paths.project_root / ".env",
        _env_file_encoding="utf-8",
        **values,
    )
