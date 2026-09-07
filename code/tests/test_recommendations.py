"""Pre-Day-10 runtime recommendation workflow and isolation tests."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.dependencies import get_recommendation_service, get_v2_artifacts
from backend.main import app
from backend.repositories.recommendations import RecommendationRepository
from backend.services.recommendations import RecommendationService


@pytest.fixture()
def recommendation_context(tmp_path: Path):
    service = RecommendationService(
        get_v2_artifacts(), RecommendationRepository(tmp_path / "runtime")
    )
    app.dependency_overrides[get_recommendation_service] = lambda: service
    with TestClient(app) as client:
        yield client, service
    app.dependency_overrides.pop(get_recommendation_service, None)


def _scopes(service: RecommendationService) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    work = service.profile.iloc[0]
    mp = {"role": "MP", "mp_id": str(work["mp_id"])}
    district = {
        "role": "DISTRICT", "state": str(work["state_name"]),
        "district": str(work["district"]),
    }
    other = service.profile.loc[
        ~service.profile["district"].eq(work["district"])
    ].iloc[0]
    wrong = {
        "role": "DISTRICT", "state": str(other["state_name"]),
        "district": str(other["district"]),
    }
    return mp, district, wrong


def _payload(service: RecommendationService) -> dict:
    work = service.profile.iloc[0]
    return {
        "title": "Community sanitation facility",
        "sector": str(work["sector"]),
        "sub_sector": str(work["sub_sector"]),
        "description": "Build a public sanitation facility for the local community.",
        "public_benefit": "Improves safe access to sanitation for residents.",
        "state": str(work["state_name"]),
        "district": str(work["district"]),
        "block": str(work["block"]),
        "village": str(work["village"]),
        "pincode": "500001",
        "latitude": float(work["registered_latitude"]),
        "longitude": float(work["registered_longitude"]),
        "proposed_project_cost_inr": 2_500_000,
        "expected_duration_months": 12,
        "preferred_start_period": "2027 Q1",
    }


def _create(client: TestClient, service: RecommendationService, *, suffix: str = "") -> tuple[dict, dict[str, str], dict[str, str]]:
    mp, district, _ = _scopes(service)
    payload = _payload(service)
    if suffix:
        payload["title"] += suffix
    response = client.post("/api/v1/recommendations", params=mp, json=payload)
    assert response.status_code == 201, response.text
    return response.json(), mp, district


def _prepare_submitted(client: TestClient, service: RecommendationService) -> tuple[str, dict[str, str], dict[str, str]]:
    record, mp, district = _create(client, service)
    recommendation_id = record["recommendation_id"]
    checked = client.post(f"/api/v1/recommendations/{recommendation_id}/precheck", params=mp)
    assert checked.status_code == 200, checked.text
    submitted = client.post(
        f"/api/v1/recommendations/{recommendation_id}/actions",
        params=mp,
        json={"action": "SUBMIT", "actor_label": "MP Office"},
    )
    assert submitted.status_code == 200, submitted.text
    return recommendation_id, mp, district


def test_mp_creates_unique_draft_ids(recommendation_context) -> None:
    client, service = recommendation_context
    first, mp, _ = _create(client, service)
    second = client.post(
        "/api/v1/recommendations", params=mp,
        json={**_payload(service), "title": "Public sanitation block extension"},
    )
    assert second.status_code == 201
    assert first["recommendation_id"] == "REC-000001"
    assert second.json()["recommendation_id"] == "REC-000002"
    assert first["status"] == "DRAFT"


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"title": ""}, "title"),
        ({"proposed_project_cost_inr": -1}, "proposed_project_cost_inr"),
        ({"latitude": 91}, "latitude"),
        ({"longitude": None}, "longitude"),
    ],
)
def test_required_cost_and_coordinate_validation(recommendation_context, changes, field) -> None:
    client, service = recommendation_context
    mp, _, _ = _scopes(service)
    response = client.post(
        "/api/v1/recommendations", params=mp, json={**_payload(service), **changes}
    )
    assert response.status_code == 422
    assert field in response.text


def test_scope_is_enforced_for_mp_and_district(recommendation_context) -> None:
    client, service = recommendation_context
    record, mp, district = _create(client, service)
    _, _, wrong = _scopes(service)
    recommendation_id = record["recommendation_id"]
    assert client.get("/api/v1/recommendations", params=mp).json()["total"] == 1
    assert client.get("/api/v1/recommendations", params=district).json()["total"] == 1
    forbidden = client.get(f"/api/v1/recommendations/{recommendation_id}", params=wrong)
    assert forbidden.status_code == 403


def test_precheck_is_bounded_ground_truth_free_and_auditable(recommendation_context) -> None:
    client, service = recommendation_context
    record, mp, _ = _create(client, service)
    response = client.post(
        f"/api/v1/recommendations/{record['recommendation_id']}/precheck", params=mp
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["precheck_version"] == "RECOMMENDATION_PRECHECK_V1"
    assert result["overall_status"] in {"Looks Good", "Check Required", "Missing Details"}
    assert len(result["similar_works"]["items"]) <= 5
    serialized = json.dumps(result).casefold()
    for prohibited in (
        "ground_truth", "duplicate_group", "embedding", "sentence-transformer",
        "provider", "groq", "model_name", "prompt",
    ):
        assert prohibited not in serialized


def test_clarification_and_acceptance_workflow(recommendation_context) -> None:
    client, service = recommendation_context
    recommendation_id, mp, district = _prepare_submitted(client, service)
    clarification = client.post(
        f"/api/v1/recommendations/{recommendation_id}/actions", params=district,
        json={
            "action": "REQUEST_CLARIFICATION", "actor_label": "District Desk",
            "message": "Please provide a clearer site location.",
        },
    )
    assert clarification.status_code == 200
    assert clarification.json()["status"] == "NEEDS_CLARIFICATION"
    provided = client.post(
        f"/api/v1/recommendations/{recommendation_id}/actions", params=mp,
        json={
            "action": "PROVIDE_CLARIFICATION", "actor_label": "MP Office",
            "message": "The site is beside the village health centre.",
        },
    )
    assert provided.status_code == 200
    accepted = client.post(
        f"/api/v1/recommendations/{recommendation_id}/actions", params=district,
        json={"action": "ACCEPT_FOR_PROCESSING", "actor_label": "District Desk"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "ACCEPTED_FOR_PROCESSING"


def test_mp_cannot_accept_or_sanction_own_recommendation(recommendation_context) -> None:
    client, service = recommendation_context
    recommendation_id, mp, _ = _prepare_submitted(client, service)
    response = client.post(
        f"/api/v1/recommendations/{recommendation_id}/actions", params=mp,
        json={"action": "ACCEPT_FOR_PROCESSING", "actor_label": "MP Office"},
    )
    assert response.status_code == 403


def test_sanction_progress_payment_and_activity_are_append_only(recommendation_context) -> None:
    client, service = recommendation_context
    recommendation_id, _, district = _prepare_submitted(client, service)
    assert client.post(
        f"/api/v1/recommendations/{recommendation_id}/actions", params=district,
        json={"action": "ACCEPT_FOR_PROCESSING", "actor_label": "District Desk"},
    ).status_code == 200
    sanctioned = client.post(
        f"/api/v1/recommendations/{recommendation_id}/actions", params=district,
        json={
            "action": "ADD_SANCTION", "actor_label": "District Desk",
            "sanctioned_cost_inr": 2_000_000, "sanction_date": "2026-10-01",
            "implementing_agency": "District Works Division",
            "expected_start_date": "2026-10-15", "expected_completion_date": "2027-10-15",
        },
    )
    assert sanctioned.status_code == 200
    assert sanctioned.json()["proposed_project_cost_inr"] == 2_500_000
    assert sanctioned.json()["sanctioned_cost_inr"] == 2_000_000
    progress = client.post(
        f"/api/v1/recommendations/{recommendation_id}/actions", params=district,
        json={
            "action": "UPDATE_PROGRESS", "actor_label": "District Engineer",
            "actual_start_date": "2026-10-20", "physical_progress_pct": 25,
            "financial_progress_pct": 70, "progress_note": "Foundation completed",
        },
    )
    assert progress.status_code == 200
    payment = client.post(
        f"/api/v1/recommendations/{recommendation_id}/actions", params=district,
        json={
            "action": "ADD_PAYMENT", "actor_label": "District Finance Desk",
            "payment_amount_inr": 2_100_000, "payment_release_date": "2026-11-03",
            "payment_request_date": "2026-11-02", "authorization_date": "2026-11-01",
        },
    )
    assert payment.status_code == 200
    assert {item["area"] for item in payment.json()["runtime_checks"]} >= {
        "Payments", "Payments & Progress", "Payment Dates"
    }
    activity = client.get(
        f"/api/v1/recommendations/{recommendation_id}/activity", params=district
    ).json()
    event_types = [event["event_type"] for event in activity]
    assert event_types[:3] == ["RECOMMENDATION_CREATED", "PRECHECK_COMPLETED", "SUBMIT"]
    assert event_types[-3:] == ["ADD_SANCTION", "UPDATE_PROGRESS", "ADD_PAYMENT"]


def test_tracker_and_sanction_date_validation(recommendation_context) -> None:
    client, service = recommendation_context
    recommendation_id, _, district = _prepare_submitted(client, service)
    accepted = client.post(
        f"/api/v1/recommendations/{recommendation_id}/actions", params=district,
        json={"action": "ACCEPT_FOR_PROCESSING", "actor_label": "District Desk"},
    )
    assert accepted.status_code == 200
    current = [item["key"] for item in accepted.json()["tracker"] if item["state"] == "CURRENT"]
    assert current == ["ACCEPTED_FOR_PROCESSING"]
    invalid = client.post(
        f"/api/v1/recommendations/{recommendation_id}/actions", params=district,
        json={
            "action": "ADD_SANCTION", "actor_label": "District Desk",
            "sanctioned_cost_inr": 2_000_000, "sanction_date": "2026-13-01",
            "implementing_agency": "District Works Division",
            "expected_start_date": "2027-10-15", "expected_completion_date": "2026-10-15",
        },
    )
    assert invalid.status_code == 422


def test_my_works_combines_frozen_and_runtime_without_merging_storage(recommendation_context) -> None:
    client, service = recommendation_context
    _, mp, _ = _create(client, service)
    response = client.get(
        "/api/v1/recommendations/my-works", params={**mp, "page_size": 100}
    )
    assert response.status_code == 200
    items = response.json()["items"]
    types = {row["record_type"] for row in items}
    assert types == {"ANALYTICAL_WORK", "RUNTIME_RECOMMENDATION"}
    runtime_row = next(row for row in items if row["record_type"] == "RUNTIME_RECOMMENDATION")
    assert runtime_row["cost_inr"] == 2_500_000


def test_document_upload_validation_and_path_confinement(recommendation_context) -> None:
    client, service = recommendation_context
    record, mp, _ = _create(client, service)
    recommendation_id = record["recommendation_id"]
    pdf = base64.b64encode(b"%PDF-1.4\n1 0 obj\n%%EOF").decode()
    valid = client.post(
        f"/api/v1/recommendations/{recommendation_id}/documents",
        params={**mp, "actor_label": "MP Office"},
        json={
            "document_type": "ESTIMATE", "original_filename": "estimate.pdf",
            "media_type": "application/pdf", "content_base64": pdf,
        },
    )
    assert valid.status_code == 201, valid.text
    assert "path" not in json.dumps(valid.json()).casefold()
    assert valid.json()["location_check"] == {
        "result": "Stored securely",
        "distance_km": None,
        "note": "Stored in the confined runtime document area.",
    }
    traversal = client.post(
        f"/api/v1/recommendations/{recommendation_id}/documents",
        params={**mp, "actor_label": "MP Office"},
        json={
            "document_type": "ESTIMATE", "original_filename": "../escape.pdf",
            "media_type": "application/pdf", "content_base64": pdf,
        },
    )
    assert traversal.status_code == 422
    executable = client.post(
        f"/api/v1/recommendations/{recommendation_id}/documents",
        params={**mp, "actor_label": "MP Office"},
        json={
            "document_type": "SUPPORTING_DOCUMENT", "original_filename": "run.exe",
            "media_type": "application/octet-stream", "content_base64": base64.b64encode(b"MZ").decode(),
        },
    )
    assert executable.status_code == 422


def test_oversized_upload_is_rejected(recommendation_context) -> None:
    client, service = recommendation_context
    record, mp, _ = _create(client, service)
    oversized = base64.b64encode(b"%PDF" + b"0" * 10_000_000).decode()
    response = client.post(
        f"/api/v1/recommendations/{record['recommendation_id']}/documents",
        params={**mp, "actor_label": "MP Office"},
        json={
            "document_type": "ESTIMATE", "original_filename": "large.pdf",
            "media_type": "application/pdf", "content_base64": oversized,
        },
    )
    assert response.status_code == 422


def test_runtime_workflow_does_not_modify_frozen_artifacts(recommendation_context) -> None:
    client, service = recommendation_context
    paths = [
        service.artifacts.paths.project_root / "data" / "processed-v2" / "work_profile.csv",
        service.artifacts.paths.project_root / "models" / "v2" / "duplicates" / "work_embeddings.npy",
    ]
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    _prepare_submitted(client, service)
    after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    assert before == after
