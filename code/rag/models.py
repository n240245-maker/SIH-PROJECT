"""Strict public and internal models for Day-8 explanations."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceExplanation(StrictModel):
    family: str
    finding: str
    source_evidence_codes: list[str]
    interpretation: str
    caveat: str


class GuidelineExplanation(StrictModel):
    chunk_id: str
    clause: str | None
    page: int | None
    relevance: str


class GroundedExplanation(StrictModel):
    work_id: str
    summary: str
    why_flagged: list[EvidenceExplanation]
    guideline_context: list[GuidelineExplanation]
    verification_steps: list[str]
    limitations: list[str]
    decision_statement: str


class RetrievedGuidelineChunk(StrictModel):
    chunk_id: str
    page_start: int
    page_end: int
    chapter: str
    clause_identifiers: str | None = None
    retrieval_method: str
    cosine_similarity: float | None = None
    guideline_version: str
    guideline_sha256: str
    text: str

    def metadata(self) -> dict[str, Any]:
        return self.model_dump(exclude={"text"})


class ExternalGuidelineExcerpt(StrictModel):
    """Traceable exact excerpt supplied to the external explanation provider."""

    chunk_id: str
    page: int
    chapter: str
    clause: str | None
    retrieval_method: str
    guideline_version: str
    guideline_sha256: str
    source_chunk_id: str
    source_chunk_sha256: str
    excerpt_sha256: str
    start_character_offset: int
    end_character_offset: int
    excerpt_text: str


class ExplanationResult(StrictModel):
    work_id: str
    generation_mode: str
    provider: str
    model: str
    api_status: str
    grounding_issues: list[str] = Field(default_factory=list)
    prompt_version: str
    guideline_version: str
    guideline_sha256: str
    evidence_bundle_sha256: str
    retrieved_chunk_ids: list[str]
    retrieval_query: str
    direct_chunk_ids: list[str]
    retrieved_guidelines: list[RetrievedGuidelineChunk]
    evidence_bundle: dict[str, Any]
    explanation: GroundedExplanation
    external_request_diagnostics: dict[str, Any] = Field(default_factory=dict)
