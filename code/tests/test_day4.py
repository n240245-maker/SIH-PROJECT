"""Day-4 duplicate, payment, execution, and prior-artifact guardrails."""

from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from intelligence.duplicates.detector import (
    DUPLICATE_CANDIDATE_THRESHOLD,
    build_duplicate_candidates,
    duplicate_priority_score,
    duplicate_review_policy,
)
from intelligence.duplicates.similarity import (
    amount_similarity,
    geographic_distance_km,
)
from intelligence.duplicates.text import build_duplicate_search_text
from intelligence.execution.fund_progress import (
    build_fund_progress_evidence,
    gap_persistence_statistics,
)
from intelligence.features.aggregations import released_payments_as_of
from intelligence.payments.irregularities import build_payment_irregularities


PRIOR_ARTIFACT_HASHES = {
    "data/processed/project_features.csv": "760D1D1366316C54CF928C5CCE03AD3A10F2793C0F986782477F03F6D9A77148",
    "data/processed/anomaly_scores.csv": "F65777B89067A8335AA953255C448774D7E52F08728B7455A4C9FBA7DF91D4CC",
    "code/models/anomaly/anomaly_model_metadata.json": "FA07C130E2BB37CA354922DE72F5872FA5DBE5F50FFF012A7919601E19349B1F",
    "code/models/anomaly/isolation_forest_pre_sanction.joblib": "A87EBECFA83E1DF9A52614FDCEAA038D7E7D87DEAEAF1231864CE3D1C6F54529",
    "code/models/anomaly/isolation_forest_execution.joblib": "C7267BD53FB0EEC426CE572FDBC6D17FBC9925A21485962FA20EFC3E47DEFFCD",
    "code/models/anomaly/isolation_forest_completion.joblib": "48C9C6AF5384C2C9CC19B55FD012A56CC73357F49611101FFF5A81250C78C86B",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


@pytest.fixture(scope="module")
def duplicate_artifacts(project_paths):
    processed = project_paths.processed_data_dir
    embeddings = np.load(
        processed / "duplicate_work_embeddings.npy", allow_pickle=False
    )
    metadata = json.loads(
        (processed / "duplicate_work_embeddings_metadata.json").read_text(
            encoding="utf-8"
        )
    )
    candidates = pd.read_csv(processed / "duplicate_candidates.csv")
    summary = pd.read_csv(processed / "duplicate_summary.csv")
    return embeddings, metadata, candidates, summary


def test_exactly_one_embedding_per_work(duplicate_artifacts):
    embeddings, metadata, _, summary = duplicate_artifacts
    assert embeddings.shape == (3000, 384)
    assert metadata["embedding_count"] == 3000
    assert len(metadata["work_ids"]) == len(set(metadata["work_ids"])) == 3000
    assert len(summary) == summary["work_id"].nunique() == 3000
    assert np.allclose(np.linalg.norm(embeddings, axis=1), 1.0, atol=1e-5)


def test_candidate_pairs_are_canonical_unique_and_not_self_pairs(
    duplicate_artifacts,
):
    _, _, candidates, _ = duplicate_artifacts
    assert len(candidates) == candidates["pair_id"].nunique()
    assert candidates["work_id_a"].lt(candidates["work_id_b"]).all()
    assert candidates["work_id_a"].ne(candidates["work_id_b"]).all()


def test_cosine_amount_and_candidate_scores_are_bounded(duplicate_artifacts):
    _, _, candidates, _ = duplicate_artifacts
    assert candidates["text_cosine_similarity"].between(0, 1).all()
    assert candidates["amount_similarity"].dropna().between(0, 1).all()
    assert candidates["duplicate_similarity_score_0_100"].between(0, 100).all()
    assert amount_similarity(80, 100) == pytest.approx(0.8)
    assert amount_similarity(None, 100) is None


def test_missing_coordinates_remain_missing_not_zero_distance():
    assert geographic_distance_km(None, 77.0, 20.0, 77.0) is None
    assert geographic_distance_km(95.0, 77.0, 20.0, 77.0) is None


def test_duplicate_priority_score_is_deterministic():
    components = {
        "text_cosine_similarity": 0.9,
        "location_similarity": 0.8,
        "amount_similarity": 0.7,
        "date_proximity": 0.6,
        "sector_match": 1.0,
        "sub_sector_match": 1.0,
        "implementing_agency_match": 0.0,
    }
    first = duplicate_priority_score(components)
    second = duplicate_priority_score(dict(reversed(list(components.items()))))
    assert first == second == pytest.approx(81.5)
    assert DUPLICATE_CANDIDATE_THRESHOLD == 75.0


def test_exported_duplicate_scores_still_follow_unchanged_formula(
    duplicate_artifacts,
):
    _, _, candidates, _ = duplicate_artifacts
    sampled = candidates.iloc[::137]
    for row in sampled.itertuples(index=False):
        components = {
            "text_cosine_similarity": row.text_cosine_similarity,
            "location_similarity": row.location_similarity,
            "amount_similarity": row.amount_similarity,
            "date_proximity": row.date_proximity_score,
            "sector_match": float(row.sector_match),
            "sub_sector_match": float(row.sub_sector_match),
            "implementing_agency_match": float(row.implementing_agency_match),
        }
        assert row.duplicate_similarity_score_0_100 == pytest.approx(
            duplicate_priority_score(components), abs=1e-5
        )
    assert candidates["candidate_flag"].equals(
        candidates["duplicate_similarity_score_0_100"].ge(75.0)
    )


def _passing_review_evidence() -> dict[str, object]:
    return {
        "duplicate_similarity_score_0_100": 93.0,
        "text_cosine_similarity": 0.98,
        "same_district": True,
        "same_block": True,
        "same_village": True,
        "geographic_distance_km": 0.5,
        "amount_similarity": 0.95,
        "recommendation_date_difference_days": 60,
        "sector_match": True,
        "sub_sector_match": True,
    }


def test_review_policy_is_deterministic_and_requires_all_corroborators():
    passing = _passing_review_evidence()
    assert duplicate_review_policy(passing) == duplicate_review_policy(dict(passing))
    assert duplicate_review_policy(passing)[0]

    failures = {
        "duplicate_similarity_score_0_100": 89.99,
        "text_cosine_similarity": 0.969,
        "same_district": False,
        "same_block": False,
        "same_village": False,
        "geographic_distance_km": 1.01,
        "amount_similarity": 0.899,
        "recommendation_date_difference_days": 121,
        "sector_match": False,
        "sub_sector_match": False,
    }
    for field, failing_value in failures.items():
        evidence = dict(passing)
        evidence[field] = failing_value
        selected, reason = duplicate_review_policy(evidence)
        assert not selected
        assert reason.startswith("NOT_SELECTED:")


def test_review_queue_is_a_corroborated_subset_of_retrieval(
    duplicate_artifacts,
):
    _, _, candidates, summary = duplicate_artifacts
    required = {
        "retrieval_candidate",
        "review_candidate",
        "review_policy_reason",
    }
    assert required.issubset(candidates.columns)
    assert candidates["retrieval_candidate"].all()
    assert candidates.loc[candidates["review_candidate"], "candidate_flag"].all()
    assert 0 < candidates["review_candidate"].sum() < candidates[
        "retrieval_candidate"
    ].sum()
    assert int(summary["review_candidate_count"].gt(0).sum()) == int(
        summary["review_candidate"].sum()
    )


def test_duplicate_outputs_use_review_evidence_not_identity_language(
    project_paths,
):
    processed = project_paths.processed_data_dir
    paths = (
        processed / "duplicate_candidates.csv",
        processed / "duplicate_summary.csv",
        processed / "duplicate_work_embeddings_metadata.json",
        processed / "day4_detector_summary.json",
    )
    forbidden = ("confirmed duplicate", "confirmed_duplicate")
    for path in paths:
        text = path.read_text(encoding="utf-8").casefold()
        assert not any(term in text for term in forbidden)


def test_duplicate_core_works_without_helper_column(operational_bundle):
    works = operational_bundle.works.drop(columns=["duplicate_group_reference"])
    texts = build_duplicate_search_text(works.head(2))
    assert len(texts) == 2 and texts.str.len().gt(0).all()
    retrieved = pd.DataFrame(
        {
            "work_id_a": [works.iloc[0]["work_id"]],
            "work_id_b": [works.iloc[1]["work_id"]],
            "text_cosine_similarity": [0.8],
        }
    )
    candidates, summary = build_duplicate_candidates(works, retrieved)
    assert len(candidates) == 1
    assert len(summary) == 3000


def test_production_day4_sources_have_no_helper_or_label_access(project_paths):
    directories = [
        project_paths.project_root / "code" / "intelligence" / "duplicates",
        project_paths.project_root / "code" / "intelligence" / "payments",
        project_paths.project_root / "code" / "intelligence" / "execution",
    ]
    forbidden = (
        "duplicate_group_reference",
        "07_anomaly_ground_truth",
        "load_evaluation_ground_truth",
        "injected_anomaly_",
        "expected_risk_",
    )
    for directory in directories:
        for path in directory.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert not any(term in source for term in forbidden)


def _payment_row(base: pd.Series, **updates) -> pd.Series:
    row = base.copy()
    for name, value in updates.items():
        row[name] = value
    return row


@pytest.fixture
def synthetic_payment_case(operational_bundle):
    base = operational_bundle.payments.iloc[0].copy()
    rows = [
        _payment_row(
            base,
            payment_id="TEST-P-1",
            work_id="TEST-W",
            payment_request_date=pd.Timestamp("2026-01-05"),
            authorization_date=pd.Timestamp("2026-01-04"),
            payment_release_date=pd.Timestamp("2026-01-02"),
            payment_amount_inr=0,
            payment_stage="Stage 1",
            payment_status="Released",
            pfms_reference="TEST-PFMS-DUP",
            is_final_payment=True,
        ),
        _payment_row(
            base,
            payment_id="TEST-P-2",
            work_id="TEST-W",
            payment_request_date=pd.Timestamp("2026-01-02"),
            authorization_date=pd.Timestamp("2026-01-02"),
            payment_release_date=pd.Timestamp("2026-01-03"),
            payment_amount_inr=150,
            payment_stage="Stage 2",
            payment_status="Released",
            pfms_reference="TEST-PFMS-DUP",
            is_final_payment=False,
        ),
        _payment_row(
            base,
            payment_id="TEST-P-10",
            work_id="TEST-W",
            payment_request_date=pd.Timestamp("2026-01-02"),
            authorization_date=pd.Timestamp("2026-01-02"),
            payment_release_date=pd.Timestamp("2026-01-03"),
            payment_amount_inr=25,
            payment_stage="Stage 10",
            payment_status="Released",
            pfms_reference="TEST-PFMS-10",
            is_final_payment=True,
        ),
        _payment_row(
            base,
            payment_id="TEST-P-FUTURE",
            work_id="TEST-W",
            payment_request_date=pd.Timestamp("2026-01-01"),
            authorization_date=pd.Timestamp("2026-01-01"),
            payment_release_date=pd.Timestamp("2027-01-01"),
            payment_amount_inr=999,
            payment_stage="Stage 3",
            payment_status="Released",
            pfms_reference="TEST-PFMS-FUTURE",
            is_final_payment=False,
        ),
    ]
    payments = pd.DataFrame(rows).reset_index(drop=True)
    features = pd.DataFrame(
        {
            "work_id": ["TEST-W"],
            "sanctioned_amount_inr": [100.0],
            "completion_date_as_of": ["2026-01-01"],
        }
    )
    return payments, features


def test_canonical_numeric_stage_order_and_future_exclusion(synthetic_payment_case):
    payments, _ = synthetic_payment_case
    visible = released_payments_as_of(payments, date(2026, 9, 1))
    assert visible["payment_id"].tolist() == ["TEST-P-1", "TEST-P-2", "TEST-P-10"]
    assert "TEST-P-FUTURE" not in set(visible["payment_id"])


def test_payment_signal_detection(synthetic_payment_case):
    payments, features = synthetic_payment_case
    evidence, summary = build_payment_irregularities(
        payments, features, date(2026, 9, 1)
    )
    counts = evidence["signal_code"].value_counts().to_dict()
    assert counts == {
        "PAYMENT_AFTER_COMPLETION": 3,
        "PAYMENT_AFTER_FINAL_PAYMENT": 2,
        "PAYMENT_AUTH_BEFORE_REQUEST": 1,
        "PAYMENT_RELEASE_BEFORE_AUTH": 1,
        "ZERO_VALUE_RELEASED_PAYMENT": 1,
        "DUPLICATE_PFMS_REFERENCE": 1,
        "MULTIPLE_FINAL_PAYMENTS": 1,
        "RELEASED_TOTAL_EXCEEDS_SANCTION": 1,
    }
    assert "TEST-P-FUTURE" not in set(evidence["payment_id"].dropna())
    assert summary.loc[0, "payment_irregularity_evidence_count"] == 11


def test_gap_persistence_calculation():
    stats = gap_persistence_statistics(pd.Series([30, 40, 0, 26, 27, 28]))
    assert stats["large_gap_report_count"] == 5
    assert stats["maximum_consecutive_large_gap_count"] == 3
    assert stats["latest_consecutive_large_gap_count"] == 3
    assert stats["latest_gap"] == 28


def test_fund_progress_formula_denominator_persistence_and_reconciliation():
    features = pd.DataFrame(
        {
            "work_id": ["W-VALID", "W-ZERO"],
            "lifecycle_stage": ["EXECUTION", "PRE_SANCTION"],
            "source_current_status": ["Ongoing", "Recommended"],
            "sanctioned_amount_inr": [200.0, 0.0],
            "released_payment_count_as_of": [2, 0],
            "released_payment_total_inr_as_of": [100.0, 0.0],
            "latest_physical_progress_pct_as_of": [20.0, np.nan],
            "latest_financial_progress_pct_as_of": [30.0, np.nan],
            "progress_report_count_as_of": [6, 0],
        }
    )
    gaps = [30, 40, 0, 26, 27, 28]
    progress = pd.DataFrame(
        {
            "work_id": ["W-VALID"] * 6,
            "progress_id": [f"PR-{index}" for index in range(6)],
            "report_date": pd.date_range("2026-01-01", periods=6, freq="D"),
            "physical_progress_pct": [10.0] * 6,
            "financial_progress_pct": [10.0 + gap for gap in gaps],
        }
    )
    evidence = build_fund_progress_evidence(
        features, progress, date(2026, 9, 1)
    )
    assert evidence["work_id"].tolist() == ["W-VALID"]
    row = evidence.iloc[0]
    assert row["payment_based_financial_progress_pct_as_of"] == pytest.approx(50.0)
    assert row["fund_minus_physical_gap_pct_as_of"] == pytest.approx(30.0)
    assert row["reported_financial_minus_physical_gap_pct_as_of"] == pytest.approx(10.0)
    assert row["reported_vs_payment_financial_progress_difference_pct"] == pytest.approx(-20.0)
    assert row["max_consecutive_large_gap_reports"] == 3
    assert bool(row["persistent_large_reported_gap_review_heuristic"])


def test_day4_outputs_do_not_create_final_risk_fields(project_paths):
    processed = project_paths.processed_data_dir
    csv_paths = (
        processed / "duplicate_candidates.csv",
        processed / "duplicate_summary.csv",
        processed / "payment_irregularities.csv",
        processed / "payment_irregularity_summary.csv",
        processed / "fund_progress_evidence.csv",
    )
    forbidden = {"risk_score", "risk_class"}
    for path in csv_paths:
        columns = {name.lower() for name in pd.read_csv(path, nrows=1).columns}
        assert columns.isdisjoint(forbidden)
    summary = json.loads(
        (processed / "day4_detector_summary.json").read_text(encoding="utf-8")
    )
    assert forbidden.isdisjoint({str(key).lower() for key in summary})


def test_prior_artifact_hashes_are_unchanged(project_paths):
    for relative_path, expected in PRIOR_ARTIFACT_HASHES.items():
        assert _sha256(project_paths.project_root / relative_path) == expected
