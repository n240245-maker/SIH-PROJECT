"""Shared fixtures for the fixed Day-1 demonstration dataset."""

from __future__ import annotations

from datetime import date

import pytest

from intelligence.data.loader import load_operational_data
from intelligence.data.paths import ProjectPaths
from intelligence.data.validation import validate_operational_data
from intelligence.features.builder import build_project_features
from intelligence.features.catalog import build_feature_catalog
from rag.evidence import ArtifactRepository
from rag.retrieval import GuidelineRetriever


SNAPSHOT_DATE = date(2026, 9, 1)


@pytest.fixture(scope="session")
def project_paths() -> ProjectPaths:
    return ProjectPaths.discover()


@pytest.fixture(scope="session")
def operational_bundle(project_paths: ProjectPaths):
    return load_operational_data(project_paths)


@pytest.fixture(scope="session")
def validation_result(operational_bundle):
    return validate_operational_data(
        operational_bundle,
        as_of_date=SNAPSHOT_DATE,
    )


@pytest.fixture(scope="session")
def snapshot_date() -> date:
    return SNAPSHOT_DATE


@pytest.fixture(scope="session")
def feature_table(operational_bundle, snapshot_date):
    return build_project_features(operational_bundle, snapshot_date)


@pytest.fixture(scope="session")
def feature_catalog():
    return build_feature_catalog()


@pytest.fixture(scope="session")
def day8_repository(project_paths):
    return ArtifactRepository(project_paths)


@pytest.fixture(scope="session")
def day8_retriever(project_paths):
    return GuidelineRetriever(project_paths)
