from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.dependencies import get_artifacts, get_reviews
from backend.main import app
from backend.repositories import ReviewRepository


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as instance:
        yield instance


def test_health_and_meta_are_governed_and_secret_free(client: TestClient) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["work_count"] == 3_000
    assert health.json()["application"] == "TRACE-X KAVACH"
    meta = client.get("/api/v1/meta")
    assert meta.status_code == 200
    assert meta.json()["risk_fusion_policy_version"] == "REVIEW_PRIORITY_POLICY_V0_1"
    assert "api_key" not in meta.text.casefold()
    assert client.get("/openapi.json").json()["info"]["title"] == "TRACE-X KAVACH API"


@pytest.mark.parametrize(
    "query",
    ["role=STATE", "role=DISTRICT&state=Odisha", "role=MP"],
)
def test_incomplete_role_scope_is_rejected(client: TestClient, query: str) -> None:
    assert client.get(f"/api/v1/dashboard/overview?{query}").status_code == 422


def test_scope_options_and_state_scope(client: TestClient) -> None:
    options = client.get("/api/v1/scope/options").json()
    assert options["roles"] == ["MOSPI", "STATE", "DISTRICT", "MP"]
    state = options["states"][0]
    scoped = client.get("/api/v1/dashboard/overview", params={"role": "STATE", "state": state})
    assert scoped.status_code == 200
    assert 0 < scoped.json()["work_count"] < 3_000


def test_queue_is_paginated_and_deterministically_sorted(client: TestClient) -> None:
    response = client.get("/api/v1/review-queue", params={"page_size": 25})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1_104
    assert len(body["items"]) == 25
    ordering = [(item["review_priority_score_0_100"], item["work_id"]) for item in body["items"]]
    assert ordering == sorted(ordering, key=lambda item: (-item[0], item[1]))


def test_complete_work_detail_reconciles_priority_and_bounds_evidence(client: TestClient) -> None:
    response = client.get("/api/v1/works/W-001937")
    assert response.status_code == 200
    body = response.json()
    assert body["contribution_sum"] == pytest.approx(body["priority"]["review_priority_score_0_100"])
    assert len(body["peer_benchmark"]["top_deviations"]) <= 10
    assert all(item["review_candidate"] is True for item in body["duplicates"]["review_candidates"])
    assert body["prediction"]["scores"]["delay_probability_calibrated"] is None
    assert "unavailable" in body["prediction"]["delay_note"].casefold()
    assert body["explanation"]["generation_mode"] == "DETERMINISTIC_FALLBACK"


def test_unknown_work_is_404(client: TestClient) -> None:
    assert client.get("/api/v1/works/W-NOT-REAL").status_code == 404


def test_work_alerts_are_scoped_filtered_and_bounded(client: TestClient) -> None:
    response = client.get("/api/v1/alerts", params={
        "alert_type": "COMPLIANCE", "minimum_strength": 50, "limit": 10})
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) <= 10
    assert all(item["alert_type"] == "COMPLIANCE" for item in body["items"])
    assert all(item["alert_strength_0_100"] >= 50 for item in body["items"])


def test_default_explanation_never_calls_provider(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_called():
        raise AssertionError("provider service must remain lazy")
    monkeypatch.setattr("backend.routers.explanations.get_explanation_service", fail_if_called)
    response = client.post("/api/v1/works/W-001937/explain", json={"use_llm": False})
    assert response.status_code == 200
    assert response.json()["api_status"] == "OFFLINE_DEFAULT"
    assert response.json()["fallback_used"] is True


def test_explicit_explanation_failure_is_safe_fallback(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable():
        raise RuntimeError("sensitive provider detail")
    monkeypatch.setattr("backend.routers.explanations.get_explanation_service", unavailable)
    response = client.post("/api/v1/works/W-001937/explain", json={"use_llm": True})
    assert response.status_code == 200
    assert response.json()["api_status"] == "FALLBACK_SERVICE_UNAVAILABLE"
    assert "sensitive provider detail" not in response.text


def test_reviews_are_append_only_and_audited(client: TestClient, tmp_path: Path) -> None:
    repository = ReviewRepository(tmp_path)
    app.dependency_overrides[get_reviews] = lambda: repository
    try:
        payload = {"actor_role": "MOSPI", "actor_label": "Demo review desk",
                   "status": "IN_REVIEW", "follow_up_action": "REQUEST_SUPPORTING_DOCUMENTS",
                   "scope_label": "MOSPI · National", "note": "Verify source documents."}
        created = client.post("/api/v1/works/W-001937/reviews", json=payload)
        assert created.status_code == 201
        assert created.json()["follow_up_action"] == "REQUEST_SUPPORTING_DOCUMENTS"
        assert created.json()["scope_label"] == "MOSPI · National"
        listed = client.get("/api/v1/works/W-001937/reviews")
        assert listed.status_code == 200 and len(listed.json()) == 1
        assert repository.reviews_path.read_text(encoding="utf-8").count("\n") == 1
        assert repository.audit_path.read_text(encoding="utf-8").count("\n") == 1
    finally:
        app.dependency_overrides.clear()


def test_review_validation_and_ground_truth_isolation(client: TestClient) -> None:
    invalid = client.post("/api/v1/works/W-001937/reviews", json={
        "actor_role": "MOSPI", "actor_label": "x", "status": "DECIDED",
        "follow_up_action": "INVENTED_ACTION", "note": "x"})
    assert invalid.status_code == 422
    openapi = client.get("/openapi.json").text.casefold()
    assert "ground_truth" not in openapi
    assert "injected_anomaly" not in openapi
