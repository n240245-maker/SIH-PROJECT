"""Append-only human-review workflow endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import get_artifacts, get_reviews
from backend.repositories import ApplicationArtifactRepository, ReviewRepository
from backend.schemas import ReviewCreate, ReviewResponse

router = APIRouter(prefix="/api/v1/works", tags=["reviews"])


@router.get("/{work_id}/reviews", response_model=list[ReviewResponse])
def list_reviews(work_id: str, artifacts: ApplicationArtifactRepository = Depends(get_artifacts),
                 reviews: ReviewRepository = Depends(get_reviews)) -> list[dict]:
    if work_id not in artifacts.work_ids:
        raise HTTPException(404, "Work was not found")
    return reviews.list_for_work(work_id)


@router.post("/{work_id}/reviews", response_model=ReviewResponse, status_code=201)
def create_review(work_id: str, payload: ReviewCreate,
                  artifacts: ApplicationArtifactRepository = Depends(get_artifacts),
                  reviews: ReviewRepository = Depends(get_reviews)) -> dict:
    if work_id not in artifacts.work_ids:
        raise HTTPException(404, "Work was not found")
    return reviews.append(work_id, payload.model_dump(mode="json"))

