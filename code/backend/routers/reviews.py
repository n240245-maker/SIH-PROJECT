"""Append-only human-review workflow endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from backend.authorization import request_scope
from backend.dependencies import get_application_service, get_reviews
from backend.repositories import ApplicationArtifactRepository, ReviewRepository
from backend.schemas import ReviewCreate, ReviewResponse
from backend.services import ApplicationService, Scope

router = APIRouter(prefix="/api/v1/works", tags=["reviews"])


@router.get("/{work_id}/reviews", response_model=list[ReviewResponse])
def list_reviews(work_id: str, scope: Scope = Depends(request_scope),
                 service: ApplicationService = Depends(get_application_service),
                 reviews: ReviewRepository = Depends(get_reviews)) -> list[dict]:
    try:
        service.authorize_work(work_id, scope)
    except KeyError:
        raise HTTPException(404, "Work was not found")
    return reviews.list_for_work(work_id)


@router.post("/{work_id}/reviews", response_model=ReviewResponse, status_code=201)
def create_review(work_id: str, payload: ReviewCreate,
                  scope: Scope = Depends(request_scope),
                  service: ApplicationService = Depends(get_application_service),
                  reviews: ReviewRepository = Depends(get_reviews)) -> dict:
    try:
        service.authorize_work(work_id, scope)
    except KeyError:
        raise HTTPException(404, "Work was not found")
    return reviews.append(work_id, payload.model_dump(mode="json"))

