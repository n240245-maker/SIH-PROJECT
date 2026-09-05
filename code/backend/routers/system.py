"""Health, metadata, and scope-option endpoints."""

from fastapi import APIRouter, Depends

from backend.config import AppSettings, get_settings
from backend.dependencies import get_application_service, get_artifacts, get_v2_artifacts
from backend.repositories import ApplicationArtifactRepository
from backend.repositories.v2_artifacts import V2ArtifactRepository
from backend.schemas import HealthResponse
from backend.services import ApplicationService

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health(artifacts: ApplicationArtifactRepository = Depends(get_artifacts),
           settings: AppSettings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(status="ok", application=settings.app_name,
                          artifact_status="validated", work_count=len(artifacts.work_ids),
                          as_of_date=settings.as_of_date)


@router.get("/api/v1/meta")
def meta(artifacts: ApplicationArtifactRepository = Depends(get_artifacts),
         settings: AppSettings = Depends(get_settings)) -> dict:
    return {"application": settings.app_name,
            "subtitle": "AI-Powered Monitoring & Decision Support",
            "api_version": "v1", "as_of_date": settings.as_of_date,
            "work_count": len(artifacts.work_ids),
            "risk_fusion_policy_version": artifacts.policy["policy_version"],
            "guideline_version": artifacts.guideline_manifest["guideline_version"],
            "guideline_sha256": artifacts.guideline_manifest["sha256"],
            "explanation_provider": "groq",
            "explanation_model": artifacts.day8_summary["configured_model"],
            "default_explanation_mode": "DETERMINISTIC_FALLBACK",
            "governance": "Decision support for human review; no output is a verdict."}


@router.get("/api/v1/scope/options")
def scope_options(service: ApplicationService = Depends(get_application_service)) -> dict:
    return service.scope_options()


@router.get("/api/v2/meta")
def v2_meta(
    artifacts: V2ArtifactRepository = Depends(get_v2_artifacts),
    settings: AppSettings = Depends(get_settings),
) -> dict:
    return {
        "application": settings.app_name,
        "api_version": "v2",
        "dataset_profile": "demo_v2",
        "synthetic_demo_data": True,
        "synthetic_disclaimer": artifacts.dataset_metadata["disclaimer"],
        "work_count": len(artifacts.work_ids),
        "model_version": artifacts.cost_evaluation["model_version"],
        "selected_cost_model": artifacts.cost_evaluation["selected_model"],
        "cost_model_quality": artifacts.cost_evaluation["model_quality_status"],
        "risk_fusion_policy_version": artifacts.policy["policy_version"],
        "guideline_version": artifacts.guideline_manifest["guideline_version"],
        "guideline_sha256": artifacts.guideline_manifest["sha256"],
        "governance": "Decision support for human review; no output is a verdict.",
    }
