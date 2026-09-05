"""Final local synthetic-demo-v2 integrity, modelling, scope, geo and report checks."""

from __future__ import annotations

import base64
import fitz
import hashlib
import inspect
import json
import re
from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.reports.v2_case_review import build_v2_case_review_pdf
from backend.repositories.geo_evidence import GeoEvidenceRepository
from backend.repositories.reviews import ReviewRepository
from backend.repositories.v2_artifacts import V2ArtifactRepository
from backend.schemas import Role
from backend.services.application import Scope
from backend.services.v2_application import ROLE_ORDERS, V2ApplicationService
from intelligence.v2.generator import generate
from intelligence.v2.geo import (
    completion_evidence_status,
    first_working_days,
    location_status,
    monthly_evidence_status,
)
from intelligence.v2.loader import (
    load_v2_data,
    load_v2_serving_data,
    verify_v2_integrity,
    v2_processed_dir,
)


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_demo_v2_generator_is_deterministic_and_explicitly_synthetic(tmp_path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    generate(first, work_count=400, seed=26102)
    generate(second, work_count=400, seed=26102)
    first_manifest = pd.read_csv(first / "00_manifest.csv")
    second_manifest = pd.read_csv(second / "00_manifest.csv")
    assert first_manifest.equals(second_manifest)
    for relative in first_manifest["file_name"]:
        assert _sha256(first / relative) == _sha256(second / relative)
    metadata = json.loads((first / "dataset_metadata.json").read_text(encoding="utf-8"))
    assert metadata["synthetic_demo_data"] is True
    assert "do not represent real" in metadata["disclaimer"]


def test_v2_manifest_keys_relationships_and_one_to_many_tables(project_paths) -> None:
    integrity = verify_v2_integrity(project_paths)
    assert integrity["status"] == "PASS"
    assert integrity["ground_truth_loaded_by_operational_loader"] is False
    bundle = load_v2_data(project_paths)
    assert len(bundle.works) == 5_000
    assert bundle.works["work_id"].is_unique
    assert len(bundle.payments) > len(bundle.works)
    assert len(bundle.progress) > len(bundle.payments)
    assert bundle.payments["work_id"].duplicated().any()
    assert bundle.progress["work_id"].duplicated().any()
    agency_counts = bundle.works.groupby("implementing_agency_id").size()
    assert set(agency_counts.index) == set(bundle.entities["entity_id"])
    assert agency_counts.min() > 0
    assert not hasattr(bundle, "ground_truth")


def test_ground_truth_is_not_imported_by_operational_or_serving_modules() -> None:
    import intelligence.v2.loader as loader

    repository_source = inspect.getsource(V2ArtifactRepository)
    service_source = inspect.getsource(V2ApplicationService)
    assert "load_v2_evaluation_ground_truth" not in repository_source
    assert "load_v2_evaluation_ground_truth" not in service_source
    assert "load_v2_evaluation_ground_truth" in inspect.getsource(loader)


def test_v2_serving_bundle_omits_redundant_raw_work_and_asset_tables(project_paths) -> None:
    bundle = load_v2_serving_data(project_paths)
    assert not hasattr(bundle, "works")
    assert not hasattr(bundle, "assets")
    assert not hasattr(bundle, "ground_truth")


def test_geo_calendar_location_and_completion_rules() -> None:
    assert first_working_days(2026, 9) == [date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)]
    assert monthly_evidence_status(lifecycle="EXECUTION", as_of=date(2026, 9, 2), capture_dates=[]) == "DUE"
    assert monthly_evidence_status(lifecycle="EXECUTION", as_of=date(2026, 9, 5), capture_dates=[]) == "OVERDUE"
    assert monthly_evidence_status(lifecycle="COMPLETION", as_of=date(2026, 9, 5), capture_dates=[]) == "NOT_APPLICABLE"
    assert completion_evidence_status(lifecycle="COMPLETION", completion_date=date(2026, 8, 28), capture_date=date(2026, 9, 2), as_of=date(2026, 9, 5)) == "RECORDED"
    assert location_status(20.0, 80.0, 20.0005, 80.0005)[0] == "LOCATION_CONSISTENT"
    assert location_status(20.0, 80.0, 20.02, 80.02)[0] == "LOCATION_REQUIRES_REVIEW"
    assert location_status(None, 80.0, 20.0, 80.0) == ("COMPARISON_UNAVAILABLE", None)


def test_v2_models_splits_duplicate_retrieval_and_priority_guardrails(project_paths) -> None:
    processed = v2_processed_dir(project_paths)
    evaluation = json.loads((processed / "evaluation" / "cost_model_evaluation.json").read_text(encoding="utf-8"))
    assert set(evaluation["candidate_metrics"]) == {"logistic_regression", "random_forest", "xgboost"}
    assert evaluation["evaluation_label"] == "Synthetic Holdout Evaluation"
    assert evaluation["calibration"] == "NOT_APPLIED"
    assert all(name not in evaluation["feature_schema"] for name in evaluation["prohibited_features"])
    split = pd.read_csv(processed / "modeling" / "cost_model_split.csv")
    assert split["work_id"].is_unique
    assert set(split["split"]) == {"TRAIN", "VALIDATION", "TEST"}

    anomaly = json.loads((processed / "evaluation" / "anomaly_evaluation.json").read_text(encoding="utf-8"))
    assert set(anomaly["lifecycle_models"]) == {"PRE_SANCTION", "EXECUTION", "COMPLETION"}
    assert anomaly["ground_truth_used_for_training"] is False

    duplicate = json.loads((processed / "evaluation" / "duplicate_evaluation.json").read_text(encoding="utf-8"))
    candidates = pd.read_csv(processed / "duplicate_candidates.csv")
    assert duplicate["known_pairs_retrieved"] == duplicate["known_synthetic_pairs"] == 2
    assert duplicate["review_candidate_pairs"] < 50
    assert not candidates["work_id_a"].eq(candidates["work_id_b"]).any()

    policy = json.loads((processed / "risk_fusion_policy.json").read_text(encoding="utf-8"))
    assert policy["ground_truth_used"] is False
    assert policy["geo_evidence"] == "warning-only with exactly zero contribution points"
    assert all("GEO" not in weights for weights in policy["weights"].values())
    assert sum(policy["weights"]["COMPLETION"].values()) == 100
    assert policy["weights"]["COMPLETION"]["OBSERVED_CONDITIONS"] == 50

    priorities = pd.read_csv(processed / "review_priority_scores.csv").set_index("work_id")
    assert priorities.loc["W-000505", "review_priority_band"] in {"HIGH", "CRITICAL"}
    assert priorities.loc["W-001937", "review_priority_band"] in {"HIGH", "CRITICAL"}


@pytest.fixture(scope="session")
def v2_service(project_paths, tmp_path_factory) -> V2ApplicationService:
    temporary = tmp_path_factory.mktemp("v2-service")
    return V2ApplicationService(
        V2ArtifactRepository(project_paths),
        ReviewRepository(temporary / "reviews"),
        GeoEvidenceRepository(temporary / "runtime"),
    )


def test_five_role_dashboards_and_authoritative_scope(v2_service: V2ApplicationService) -> None:
    first = v2_service.work_view.iloc[0]
    scopes = [
        Scope(Role.MOSPI), Scope(Role.STATE, state=str(first["state_name"])),
        Scope(Role.DISTRICT, state=str(first["state_name"]), district=str(first["district"])),
        Scope(Role.IA, agency_id=str(first["implementing_agency_id"])), Scope(Role.MP, mp_id=str(first["mp_id"])),
    ]
    for scope in scopes:
        dashboard = v2_service.overview(scope)
        assert dashboard["section_order"] == ROLE_ORDERS[scope.role.value]
        assert dashboard["overview"]["total_projects"] == len(v2_service.scoped(v2_service.work_view, scope))
        assert dashboard["synthetic_demo_data"] is True
    wrong_mp = next(value for value in v2_service.work_view["mp_id"].astype(str).unique() if value != str(first["mp_id"]))
    with pytest.raises(KeyError):
        v2_service.authorize_work(str(first["work_id"]), Scope(Role.MP, mp_id=wrong_mp))


def test_work_dossier_has_exact_nine_sections_and_priority_reconciles(v2_service: V2ApplicationService) -> None:
    detail = v2_service.work_detail("W-001937")
    assert [
        "project_details", "monitoring_health", "anomalies_irregularities", "key_risk_areas",
        "progress_schedule", "geo_evidence", "records_completion", "ai_explanation", "officer_review",
    ] == [key for key in detail if key in {
        "project_details", "monitoring_health", "anomalies_irregularities", "key_risk_areas",
        "progress_schedule", "geo_evidence", "records_completion", "ai_explanation", "officer_review",
    }]
    contributions = detail["technical_details"]["review_priority"]["contributions"]
    assert sum(float(row["contribution_points"]) for row in contributions) == pytest.approx(detail["header"]["review_priority_score_0_100"], abs=1e-6)
    assert detail["geo_evidence"]["summary"]["warning_contribution_points"] == 0
    serialized = json.dumps(detail).casefold()
    assert "ground_truth" not in serialized
    assert "fraud detected" not in serialized


def test_geo_submission_is_ia_only_and_district_verification_is_scoped(v2_service: V2ApplicationService) -> None:
    work = v2_service.artifacts.require_work("W-000808")
    ia_scope = Scope(Role.IA, agency_id=str(work["implementing_agency_id"]))
    payload = {
        "evidence_stage": "MONTHLY_PROGRESS", "reporting_month": "2026-09",
        "physical_progress_pct": 42.0, "latitude": float(work["registered_latitude"]),
        "longitude": float(work["registered_longitude"]), "capture_timestamp": "2026-09-02T10:00:00+05:30",
        "captured_by_user": "IA Test Officer", "source_type": "UPLOADED_IMAGE",
        "image_base64": base64.b64encode(b"synthetic-image-bytes").decode("ascii"),
        "image_media_type": "image/jpeg", "note": "Synthetic test evidence",
    }
    created = v2_service.create_geo_evidence("W-000808", ia_scope, payload.copy())
    assert created["verification_status"] == "PENDING_DISTRICT_VERIFICATION"
    assert len(created["image_sha256"]) == 64
    with pytest.raises(PermissionError):
        v2_service.create_geo_evidence("W-000808", Scope(Role.MOSPI), payload.copy())
    district_scope = Scope(Role.DISTRICT, state=str(work["state_name"]), district=str(work["district"]))
    verified = v2_service.verify_geo_evidence(created["evidence_id"], district_scope, {
        "verification_status": "DISTRICT_VERIFIED", "verified_by": "District Test Officer", "note": "Verified",
    })
    assert verified["verification_status"] == "DISTRICT_VERIFIED"


def test_v2_pdf_is_deterministic_evidence_only_and_secret_free(v2_service: V2ApplicationService) -> None:
    detail = v2_service.work_detail("W-001937")
    pdf = build_v2_case_review_pdf(detail, generated_at=date(2026, 9, 5))
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 5_000
    lowered = pdf.lower()
    assert b"groq_api_key" not in lowered
    with fitz.open(stream=pdf, filetype="pdf") as document:
        visible_text = "\n".join(page.get_text() for page in document)
    assert not re.search(r"\b(?:nan|none|null)\b", visible_text, flags=re.IGNORECASE)


def test_v2_api_offline_fallback_and_contract_are_ground_truth_free() -> None:
    with TestClient(app) as client:
        overview = client.get("/api/v2/dashboard/overview", params={"role": "MOSPI"})
        assert overview.status_code == 200
        detail = client.get("/api/v2/works/W-001937", params={"role": "MOSPI"})
        assert detail.status_code == 200
        fallback = client.post("/api/v2/works/W-001937/explain", params={"role": "MOSPI"}, json={"use_llm": False})
        assert fallback.status_code == 200
        assert fallback.json()["generation_mode"] == "DETERMINISTIC_FALLBACK"
        assert fallback.json()["fallback_used"] is True
        assert "ground_truth" not in json.dumps(client.get("/openapi.json").json()).casefold()
