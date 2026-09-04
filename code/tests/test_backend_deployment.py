"""Deployment-specific memory and offline-serving regressions."""

from __future__ import annotations

from backend.dependencies import get_artifacts
from backend.repositories.artifacts import IndexedJsonlMapping
from backend.services.frozen_explanations import FrozenContextExplanationService
from rag.groq_client import GroqClient, GroqSettings


def test_explanation_context_is_indexed_without_materializing_every_record(
    project_paths,
) -> None:
    mapping = IndexedJsonlMapping(
        project_paths.processed_data_dir / "explanation_context.jsonl", "work_id"
    )
    assert len(mapping) == 3_000
    assert mapping["W-001937"]["work_id"] == "W-001937"
    assert mapping["W-002760"]["work_id"] == "W-002760"


def test_frozen_context_service_preserves_governed_fallback_and_retrieval() -> None:
    artifacts = get_artifacts()
    context = artifacts.explanations["W-001937"]
    service = FrozenContextExplanationService(
        artifacts,
        GroqClient(GroqSettings(groq_api_key=None)),
    )

    result = service.explain_work("W-001937", use_llm=True)

    assert result.generation_mode == "DETERMINISTIC_FALLBACK"
    assert result.api_status == "SKIPPED_NO_GROQ_API_KEY"
    assert result.explanation.model_dump(mode="json") == context["fallback_explanation"]
    assert result.retrieved_chunk_ids == [
        row["chunk_id"] for row in context["retrieval"]["chunks"]
    ]
    assert result.evidence_bundle_sha256 == context["explanation_metadata"][
        "evidence_bundle_sha256"
    ]
