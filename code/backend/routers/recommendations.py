"""Scoped MP-to-District recommendation workflow endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.authorization import request_scope
from backend.dependencies import get_recommendation_service
from backend.schemas import (
    RecommendationActionRequest,
    RecommendationCreate,
    RecommendationDocumentUpload,
)
from backend.services import Scope
from backend.services.recommendations import RecommendationService


router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])


def _safe_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(404, "Recommendation was not found")
    if isinstance(exc, PermissionError):
        return HTTPException(403, str(exc) or "This recommendation is outside the selected scope")
    return HTTPException(422, str(exc))


@router.post("", status_code=201)
def create_recommendation(
    payload: RecommendationCreate,
    scope: Scope = Depends(request_scope),
    service: RecommendationService = Depends(get_recommendation_service),
) -> dict:
    try:
        return service.create(payload.model_dump(mode="json"), scope)
    except (KeyError, PermissionError, ValueError) as exc:
        raise _safe_error(exc) from None


@router.get("")
def list_recommendations(
    scope: Scope = Depends(request_scope),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str | None = Query(None, max_length=120),
    status: str | None = Query(None, max_length=60),
    service: RecommendationService = Depends(get_recommendation_service),
) -> dict:
    return service.list(scope, page=page, page_size=page_size, search=search, status=status)


@router.get("/my-works")
def my_works(
    scope: Scope = Depends(request_scope),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    category: str | None = Query(None, pattern=r"^(RECOMMENDED|ONGOING|COMPLETED)$"),
    search: str | None = Query(None, max_length=120),
    service: RecommendationService = Depends(get_recommendation_service),
) -> dict:
    try:
        return service.my_works(
            scope, page=page, page_size=page_size, category=category, search=search
        )
    except PermissionError as exc:
        raise _safe_error(exc) from None


@router.get("/{recommendation_id}")
def recommendation_detail(
    recommendation_id: str,
    scope: Scope = Depends(request_scope),
    service: RecommendationService = Depends(get_recommendation_service),
) -> dict:
    try:
        return service.require(recommendation_id, scope)
    except (KeyError, PermissionError) as exc:
        raise _safe_error(exc) from None


@router.post("/{recommendation_id}/precheck")
def precheck_recommendation(
    recommendation_id: str,
    scope: Scope = Depends(request_scope),
    service: RecommendationService = Depends(get_recommendation_service),
) -> dict:
    try:
        return service.precheck(recommendation_id, scope)
    except (KeyError, PermissionError, ValueError) as exc:
        raise _safe_error(exc) from None


@router.post("/{recommendation_id}/actions")
def recommendation_action(
    recommendation_id: str,
    payload: RecommendationActionRequest,
    scope: Scope = Depends(request_scope),
    service: RecommendationService = Depends(get_recommendation_service),
) -> dict:
    try:
        return service.action(recommendation_id, payload.model_dump(mode="json"), scope)
    except (KeyError, PermissionError, ValueError) as exc:
        raise _safe_error(exc) from None


@router.post("/{recommendation_id}/documents", status_code=201)
def upload_recommendation_document(
    recommendation_id: str,
    payload: RecommendationDocumentUpload,
    actor_label: str = Query(..., min_length=2, max_length=120),
    scope: Scope = Depends(request_scope),
    service: RecommendationService = Depends(get_recommendation_service),
) -> dict:
    try:
        return service.add_document(
            recommendation_id,
            payload.model_dump(mode="json"),
            scope,
            actor_label=actor_label,
        )
    except (KeyError, PermissionError, ValueError) as exc:
        raise _safe_error(exc) from None


@router.get("/{recommendation_id}/activity")
def recommendation_activity(
    recommendation_id: str,
    scope: Scope = Depends(request_scope),
    service: RecommendationService = Depends(get_recommendation_service),
) -> list[dict]:
    try:
        return service.activity(recommendation_id, scope)
    except (KeyError, PermissionError) as exc:
        raise _safe_error(exc) from None
