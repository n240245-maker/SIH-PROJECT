"""Dashboard, queue, work-detail, trend, hotspot, alert, and report routes."""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from backend.dependencies import (
    get_application_service,
    get_artifacts,
    get_validated_explanation_cache,
)
from backend.reports import build_case_review_pdf
from backend.repositories import ApplicationArtifactRepository
from backend.schemas import PageResponse, Role
from backend.services import ApplicationService, Scope
from backend.services.explanation_cache import ValidatedExplanationCache

router = APIRouter(prefix="/api/v1", tags=["intelligence"])


def scope_dependency(role: Role = Query(Role.MOSPI), state: str | None = Query(None),
                     district: str | None = Query(None), mp_id: str | None = Query(None)) -> Scope:
    scope = Scope(role=role, state=state, district=district, mp_id=mp_id)
    if role == Role.STATE and not state:
        raise HTTPException(422, "STATE role requires state")
    if role == Role.DISTRICT and (not state or not district):
        raise HTTPException(422, "DISTRICT role requires state and district")
    if role == Role.MP and not mp_id:
        raise HTTPException(422, "MP role requires mp_id")
    return scope


@router.get("/dashboard/overview")
def overview(scope: Scope = Depends(scope_dependency),
             service: ApplicationService = Depends(get_application_service)) -> dict:
    return service.overview(scope)


@router.get("/review-queue", response_model=PageResponse)
def review_queue(scope: Scope = Depends(scope_dependency), page: int = Query(1, ge=1),
                 page_size: int = Query(25, ge=1, le=100), search: str | None = Query(None, max_length=120),
                 lifecycle: str | None = None, band: str | None = None, sector: str | None = None,
                 attention_level: str | None = None, review_need: str | None = None,
                 sub_sector: str | None = None, alert_type: str | None = None,
                 duplicate: bool | None = None, compliance: bool | None = None,
                 overdue: bool | None = None, over_sanction: bool | None = None,
                 review_status: str | None = None, sort_by: str = "score", sort_order: str = "desc",
                 service: ApplicationService = Depends(get_application_service)) -> dict:
    return service.review_queue(scope, page=page, page_size=page_size, search=search,
        lifecycle=lifecycle, band=band, attention_level=attention_level, review_need=review_need,
        sector=sector, sub_sector=sub_sector,
        alert_type=alert_type, duplicate=duplicate, compliance=compliance, overdue=overdue,
        over_sanction=over_sanction, review_status=review_status, sort_by=sort_by, sort_order=sort_order)


@router.get("/works/{work_id}")
def work_detail(work_id: str, service: ApplicationService = Depends(get_application_service)) -> dict:
    try:
        return service.work_detail(work_id)
    except KeyError:
        raise HTTPException(404, "Work was not found") from None


@router.get(
    "/works/{work_id}/case-report.pdf",
    response_class=Response,
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "Offline-capable case review support report",
        },
        404: {"description": "Work was not found"},
    },
)
def case_report(
    work_id: str,
    service: ApplicationService = Depends(get_application_service),
    artifacts: ApplicationArtifactRepository = Depends(get_artifacts),
    cache: ValidatedExplanationCache = Depends(get_validated_explanation_cache),
) -> Response:
    try:
        detail = service.work_detail(work_id)
    except KeyError:
        raise HTTPException(404, "Work was not found") from None
    cached = cache.get(work_id, artifacts)
    if cached is None:
        context = artifacts.explanations[work_id]
        explanation = {
            "generation_mode": "DETERMINISTIC_FALLBACK",
            "api_status": "OFFLINE_REPORT",
            "explanation": context["fallback_explanation"],
        }
    else:
        explanation = cached
    generated_at = datetime.now(ZoneInfo("Asia/Kolkata"))
    content = build_case_review_pdf(detail, explanation, generated_at)
    filename = f"MPLADS_Sentinel_Case_{work_id}_{generated_at:%Y-%m-%d}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/trends")
def trends(scope: Scope = Depends(scope_dependency), metric: str | None = None,
           group_type: str | None = None, state_filter: str | None = None,
           district_filter: str | None = None, sector: str | None = None,
           date_from: str | None = None, date_to: str | None = None,
           limit: int = Query(500, ge=1, le=2000),
           service: ApplicationService = Depends(get_application_service)) -> dict:
    return service.trends(scope, metric=metric, group_type=group_type, state=state_filter,
        district=district_filter, sector=sector, date_from=date_from, date_to=date_to, limit=limit)


@router.get("/hotspots")
def hotspots(scope: Scope = Depends(scope_dependency), group_type: str | None = None,
             limit: int = Query(100, ge=1, le=500),
             service: ApplicationService = Depends(get_application_service)) -> dict:
    return service.aggregated("hotspots", scope, group_type=group_type, alert_type=None, limit=limit)


@router.get("/alerts")
def alerts(scope: Scope = Depends(scope_dependency), alert_type: str | None = None,
           lifecycle: str | None = None,
           minimum_strength: float = Query(0, ge=0, le=100),
           limit: int = Query(200, ge=1, le=1000),
           service: ApplicationService = Depends(get_application_service)) -> dict:
    return service.alerts(scope, alert_type=alert_type, lifecycle=lifecycle,
                          minimum_strength=minimum_strength, limit=limit)
