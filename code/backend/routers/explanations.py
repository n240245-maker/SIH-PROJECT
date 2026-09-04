"""Explicit, fail-closed Day-8 explanation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import (
    get_artifacts,
    get_explanation_service,
    get_validated_explanation_cache,
)
from backend.repositories import ApplicationArtifactRepository
from backend.schemas import ExplainRequest, ExplainResponse
from backend.serialization import json_safe
from backend.services.explanation_cache import ValidatedExplanationCache

router = APIRouter(prefix="/api/v1/works", tags=["explanations"])


def _frozen_fallback(work_id: str, artifacts: ApplicationArtifactRepository,
                     status: str = "OFFLINE_DEFAULT") -> dict:
    context = artifacts.explanations[work_id]
    metadata = context["explanation_metadata"]
    retrieval = context["retrieval"]
    return {"work_id": work_id, "generation_mode": "DETERMINISTIC_FALLBACK",
            "api_status": status, "provider": "groq",
            "model": metadata.get("configured_model", artifacts.day8_summary["configured_model"]),
            "explanation": context["fallback_explanation"],
            "retrieved_guidelines": retrieval.get("retrieved_guidelines", retrieval.get("chunks", [])),
            "fallback_used": True}


@router.post("/{work_id}/explain", response_model=ExplainResponse)
def explain_work(payload: ExplainRequest, work_id: str,
                 artifacts: ApplicationArtifactRepository = Depends(get_artifacts),
                 cache: ValidatedExplanationCache = Depends(get_validated_explanation_cache)) -> dict:
    if work_id not in artifacts.work_ids:
        raise HTTPException(404, "Work was not found")
    if not payload.use_llm:
        return _frozen_fallback(work_id, artifacts)
    try:
        result = get_explanation_service().explain_work(work_id, use_llm=True)
        response = json_safe({"work_id": work_id, "generation_mode": result.generation_mode,
                              "api_status": result.api_status, "provider": result.provider,
                              "model": result.model, "explanation": result.explanation.model_dump(mode="json"),
                              "retrieved_guidelines": [item.model_dump(mode="json") for item in result.retrieved_guidelines],
                              "fallback_used": result.generation_mode != "GROQ_GROUNDED"})
        cache.put(work_id, artifacts, response)
        return response
    except Exception:
        # No provider exception, payload, stack, or credential reaches the client.
        return _frozen_fallback(work_id, artifacts, "FALLBACK_SERVICE_UNAVAILABLE")
