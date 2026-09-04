"""Typed public API request and response contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Role(StrEnum):
    MOSPI = "MOSPI"
    STATE = "STATE"
    DISTRICT = "DISTRICT"
    MP = "MP"


class ReviewStatus(StrEnum):
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class ExplainRequest(BaseModel):
    use_llm: bool = False


class ReviewCreate(BaseModel):
    actor_role: Role
    actor_label: str = Field(min_length=2, max_length=120)
    status: ReviewStatus
    note: str = Field(min_length=2, max_length=2000)

    @field_validator("actor_label", "note")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class HealthResponse(BaseModel):
    status: str
    application: str
    artifact_status: str
    work_count: int
    as_of_date: str


class PageResponse(BaseModel):
    items: list[dict[str, Any]]
    page: int
    page_size: int
    total: int
    total_pages: int


class ReviewResponse(BaseModel):
    review_id: str
    work_id: str
    actor_role: Role
    actor_label: str
    status: ReviewStatus
    note: str
    created_at: str


class ExplainResponse(BaseModel):
    work_id: str
    generation_mode: str
    api_status: str
    provider: str
    model: str
    explanation: dict[str, Any]
    retrieved_guidelines: list[dict[str, Any]]
    fallback_used: bool

