"""Health, metadata, and scope-option endpoints."""

from fastapi import APIRouter, Depends

from backend.config import AppSettings, get_settings
from backend.dependencies import get_application_service, get_artifacts
from backend.repositories import ApplicationArtifactRepository
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

