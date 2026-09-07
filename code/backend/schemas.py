"""Typed public API request and response contracts."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class Role(StrEnum):
    MOSPI = "MOSPI"
    STATE = "STATE"
    DISTRICT = "DISTRICT"
    MP = "MP"
    IA = "IA"


class GeoEvidenceSource(StrEnum):
    LIVE_SITE_CAPTURE = "LIVE_SITE_CAPTURE"
    UPLOADED_IMAGE = "UPLOADED_IMAGE"


class GeoEvidenceCreate(BaseModel):
    evidence_stage: str
    reporting_month: str = Field(pattern=r"^\d{4}-\d{2}$")
    physical_progress_pct: float = Field(ge=0, le=100)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    capture_timestamp: str
    captured_by_user: str = Field(min_length=2, max_length=120)
    source_type: GeoEvidenceSource
    image_base64: str = Field(min_length=8)
    image_media_type: str = Field(pattern=r"^image/(jpeg|png|webp)$")
    note: str = Field(default="", max_length=500)


class GeoEvidenceVerify(BaseModel):
    verification_status: str = Field(pattern=r"^(DISTRICT_VERIFIED|REQUIRES_CLARIFICATION|REJECTED)$")
    verified_by: str = Field(min_length=2, max_length=120)
    note: str = Field(default="", max_length=500)


class ReviewStatus(StrEnum):
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class FollowUpAction(StrEnum):
    REQUEST_CLARIFICATION = "REQUEST_CLARIFICATION"
    REQUEST_SUPPORTING_DOCUMENTS = "REQUEST_SUPPORTING_DOCUMENTS"
    FINANCIAL_RECONCILIATION_REQUIRED = "FINANCIAL_RECONCILIATION_REQUIRED"
    REQUEST_UPDATED_PROGRESS_REPORT = "REQUEST_UPDATED_PROGRESS_REPORT"
    SCHEDULE_FIELD_VERIFICATION = "SCHEDULE_FIELD_VERIFICATION"
    DUPLICATE_WORK_COMPARISON_REQUIRED = "DUPLICATE_WORK_COMPARISON_REQUIRED"
    REVIEW_REVISED_SANCTION = "REVIEW_REVISED_SANCTION"
    ESCALATE_FOR_DETAILED_REVIEW = "ESCALATE_FOR_DETAILED_REVIEW"
    NO_FURTHER_ACTION = "NO_FURTHER_ACTION"
    CLOSE_AFTER_VERIFICATION = "CLOSE_AFTER_VERIFICATION"


class ExplainRequest(BaseModel):
    use_llm: bool = False


class RecommendationStatus(StrEnum):
    DRAFT = "DRAFT"
    RECOMMENDED = "RECOMMENDED"
    UNDER_REVIEW = "UNDER_REVIEW"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    ACCEPTED_FOR_PROCESSING = "ACCEPTED_FOR_PROCESSING"
    SANCTIONED = "SANCTIONED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CLOSED = "CLOSED"


class RecommendationAction(StrEnum):
    SUBMIT = "SUBMIT"
    REQUEST_CLARIFICATION = "REQUEST_CLARIFICATION"
    PROVIDE_CLARIFICATION = "PROVIDE_CLARIFICATION"
    ACCEPT_FOR_PROCESSING = "ACCEPT_FOR_PROCESSING"
    ADD_SANCTION = "ADD_SANCTION"
    UPDATE_PROGRESS = "UPDATE_PROGRESS"
    ADD_PAYMENT = "ADD_PAYMENT"
    MARK_COMPLETED = "MARK_COMPLETED"


class RecommendationCreate(BaseModel):
    title: str = Field(min_length=5, max_length=180)
    sector: str = Field(min_length=2, max_length=120)
    sub_sector: str = Field(min_length=2, max_length=160)
    description: str = Field(min_length=10, max_length=2000)
    public_benefit: str = Field(min_length=5, max_length=1000)
    state: str = Field(min_length=2, max_length=120)
    district: str = Field(min_length=2, max_length=160)
    block: str = Field(min_length=2, max_length=160)
    village: str = Field(min_length=2, max_length=160)
    pincode: str | None = Field(default=None, pattern=r"^\d{6}$")
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    proposed_project_cost_inr: float = Field(gt=0)
    expected_duration_months: int | None = Field(default=None, ge=1, le=120)
    preferred_start_period: str | None = Field(default=None, max_length=80)

    @field_validator(
        "title", "sector", "sub_sector", "description", "public_benefit",
        "state", "district", "block", "village", "pincode", "preferred_start_period",
    )
    @classmethod
    def clean_recommendation_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def coordinates_are_paired(self) -> "RecommendationCreate":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Latitude and longitude must be provided together")
        return self


class RecommendationActionRequest(BaseModel):
    action: RecommendationAction
    actor_label: str = Field(min_length=2, max_length=120)
    message: str | None = Field(default=None, max_length=1000)
    sanctioned_cost_inr: float | None = Field(default=None, gt=0)
    sanction_date: str | None = None
    implementing_agency: str | None = Field(default=None, max_length=200)
    expected_start_date: str | None = None
    expected_completion_date: str | None = None
    actual_start_date: str | None = None
    physical_progress_pct: float | None = Field(default=None, ge=0, le=100)
    financial_progress_pct: float | None = Field(default=None, ge=0)
    progress_note: str | None = Field(default=None, max_length=1000)
    payment_amount_inr: float | None = Field(default=None, gt=0)
    payment_release_date: str | None = None
    payment_request_date: str | None = None
    authorization_date: str | None = None

    @field_validator(
        "actor_label", "message", "implementing_agency", "progress_note",
        "sanction_date", "expected_start_date", "expected_completion_date",
        "actual_start_date", "payment_release_date", "payment_request_date",
        "authorization_date",
    )
    @classmethod
    def clean_action_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator(
        "sanction_date", "expected_start_date", "expected_completion_date",
        "actual_start_date", "payment_release_date", "payment_request_date",
        "authorization_date",
    )
    @classmethod
    def validate_iso_dates(cls, value: str | None) -> str | None:
        if value:
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("Dates must use YYYY-MM-DD format") from exc
        return value

    @model_validator(mode="after")
    def required_action_fields(self) -> "RecommendationActionRequest":
        if self.action in {RecommendationAction.REQUEST_CLARIFICATION, RecommendationAction.PROVIDE_CLARIFICATION} and not self.message:
            raise ValueError("A clarification message is required")
        if self.action == RecommendationAction.ADD_SANCTION:
            required = (self.sanctioned_cost_inr, self.sanction_date, self.implementing_agency,
                        self.expected_start_date, self.expected_completion_date)
            if any(value in {None, ""} for value in required):
                raise ValueError("Complete sanction details are required")
            if date.fromisoformat(self.expected_completion_date or "") < date.fromisoformat(self.expected_start_date or ""):
                raise ValueError("Expected completion cannot be before expected start")
        if self.action == RecommendationAction.UPDATE_PROGRESS and self.physical_progress_pct is None:
            raise ValueError("Physical progress is required")
        if self.action == RecommendationAction.ADD_PAYMENT and (
            self.payment_amount_inr is None or not self.payment_release_date
        ):
            raise ValueError("Payment amount and release date are required")
        return self


class RecommendationDocumentUpload(BaseModel):
    document_type: str = Field(min_length=2, max_length=80)
    original_filename: str = Field(min_length=1, max_length=240)
    media_type: str = Field(min_length=3, max_length=100)
    content_base64: str = Field(min_length=4, max_length=15_000_000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def upload_coordinates_are_paired(self) -> "RecommendationDocumentUpload":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Photo latitude and longitude must be provided together")
        return self


class ReviewCreate(BaseModel):
    actor_role: Role
    actor_label: str = Field(min_length=2, max_length=120)
    status: ReviewStatus
    follow_up_action: FollowUpAction
    scope_label: str | None = Field(default=None, max_length=240)
    note: str = Field(min_length=2, max_length=2000)

    @field_validator("actor_label", "note", "scope_label")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class HealthResponse(BaseModel):
    status: str
    application: str
    artifact_status: str
    work_count: int
    analytical_work_count: int | None = None
    runtime_recommendation_count: int | None = None
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
    follow_up_action: FollowUpAction | None = None
    scope_label: str | None = None
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

