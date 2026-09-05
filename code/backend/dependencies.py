"""Cached application dependencies and lazy Day-8 explanation integration."""

from __future__ import annotations

from functools import lru_cache

from backend.config import get_settings
from backend.repositories import ApplicationArtifactRepository, ReviewRepository
from backend.repositories.geo_evidence import GeoEvidenceRepository
from backend.repositories.v2_artifacts import V2ArtifactRepository
from backend.services import ApplicationService
from backend.services.v2_application import V2ApplicationService
from backend.services.explanation_cache import ValidatedExplanationCache
from intelligence.data.paths import ProjectPaths


@lru_cache(maxsize=1)
def get_artifacts() -> ApplicationArtifactRepository:
    return ApplicationArtifactRepository(ProjectPaths.discover())


@lru_cache(maxsize=1)
def get_reviews() -> ReviewRepository:
    settings = get_settings()
    assert settings.runtime_data_dir is not None
    return ReviewRepository(settings.runtime_data_dir)


@lru_cache(maxsize=1)
def get_application_service() -> ApplicationService:
    return ApplicationService(get_artifacts(), get_reviews())


@lru_cache(maxsize=1)
def get_validated_explanation_cache() -> ValidatedExplanationCache:
    return ValidatedExplanationCache()


@lru_cache(maxsize=1)
def get_v2_artifacts() -> V2ArtifactRepository:
    return V2ArtifactRepository(ProjectPaths.discover())


@lru_cache(maxsize=1)
def get_geo_evidence_repository() -> GeoEvidenceRepository:
    settings = get_settings()
    assert settings.runtime_data_dir is not None
    return GeoEvidenceRepository(
        settings.runtime_data_dir,
        max_image_bytes=settings.geo_max_image_bytes,
    )


@lru_cache(maxsize=1)
def get_v2_application_service() -> V2ApplicationService:
    return V2ApplicationService(get_v2_artifacts(), get_reviews(), get_geo_evidence_repository())


@lru_cache(maxsize=1)
def get_explanation_service():
    from backend.services.frozen_explanations import FrozenContextExplanationService
    from rag.groq_client import GroqClient, load_groq_settings

    paths = ProjectPaths.discover()
    return FrozenContextExplanationService(
        get_artifacts(),
        GroqClient(load_groq_settings(paths)),
    )
