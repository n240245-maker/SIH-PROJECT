"""Process-local cache for already validated, explicitly requested Groq output."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any

from backend.repositories import ApplicationArtifactRepository


@dataclass(frozen=True, slots=True)
class ExplanationCacheKey:
    work_id: str
    evidence_bundle_hash: str
    guideline_hash: str
    model: str
    prompt_version: str


class ValidatedExplanationCache:
    """Caches only GROQ_GROUNDED responses already accepted by Day-8 validators."""

    def __init__(self) -> None:
        self._items: dict[ExplanationCacheKey, dict[str, Any]] = {}
        self._lock = RLock()

    @staticmethod
    def key_for(work_id: str, artifacts: ApplicationArtifactRepository) -> ExplanationCacheKey:
        metadata = artifacts.explanations[work_id]["explanation_metadata"]
        return ExplanationCacheKey(
            work_id=work_id,
            evidence_bundle_hash=str(metadata["evidence_bundle_sha256"]),
            guideline_hash=str(metadata["guideline_sha256"]),
            model=str(metadata["model"]),
            prompt_version=str(metadata["prompt_version"]),
        )

    def put(self, work_id: str, artifacts: ApplicationArtifactRepository,
            response: dict[str, Any]) -> None:
        if response.get("generation_mode") != "GROQ_GROUNDED" or response.get("fallback_used") is not False:
            return
        key = self.key_for(work_id, artifacts)
        if response.get("model") != key.model:
            return
        safe = {
            "work_id": work_id,
            "generation_mode": "GROQ_GROUNDED",
            "api_status": response.get("api_status"),
            "provider": response.get("provider"),
            "model": response.get("model"),
            "explanation": response.get("explanation"),
            "retrieved_guidelines": response.get("retrieved_guidelines", []),
            "fallback_used": False,
        }
        with self._lock:
            self._items[key] = safe

    def get(self, work_id: str, artifacts: ApplicationArtifactRepository) -> dict[str, Any] | None:
        with self._lock:
            return self._items.get(self.key_for(work_id, artifacts))

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
