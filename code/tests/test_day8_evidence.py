"""Day-8 frozen evidence-bundle and minimization tests."""

from __future__ import annotations

import json

import pandas as pd


def test_priority_and_contributions_are_read_exactly(project_paths, day8_repository):
    work_id = "W-001937"
    bundle = day8_repository.build_explanation_evidence(work_id)
    scores = pd.read_csv(project_paths.processed_data_dir / "review_priority_scores.csv")
    row = scores.loc[scores["work_id"].eq(work_id)].iloc[0]
    assert bundle["review_priority"]["review_priority_score_0_100"] == row[
        "review_priority_score_0_100"
    ]
    evidence = pd.read_csv(
        project_paths.processed_data_dir / "review_priority_evidence.csv"
    )
    expected = evidence.loc[
        evidence["work_id"].eq(work_id) & evidence["contribution_points"].gt(0),
        ["family", "contribution_points"],
    ]
    actual = {
        row["family"]: row["contribution_points"]
        for row in bundle["top_contributions"]
    }
    assert actual == dict(zip(expected["family"], expected["contribution_points"], strict=True))
    assert bundle["review_priority"]["fusion_evidence_coverage_pct"] == 100
    assert bundle["governance"]["priority_read_not_recalculated"] is True


def test_only_day4_1_review_candidates_are_promoted(project_paths, day8_repository):
    pairs = pd.read_csv(project_paths.processed_data_dir / "duplicate_candidates.csv")
    broad_only = pairs.loc[pairs["candidate_flag"] & ~pairs["review_candidate"]].iloc[0]
    work_id = str(broad_only["work_id_a"])
    bundle = day8_repository.build_explanation_evidence(work_id)
    explained_ids = {
        item["pair_id"] for item in bundle["duplicate"]["review_candidates_only"]
    }
    assert broad_only["pair_id"] not in explained_ids
    assert all(
        item["review_candidate"]
        for item in bundle["duplicate"]["review_candidates_only"]
    )


def test_prediction_and_aggregate_context_boundaries(day8_repository):
    bundle = day8_repository.build_explanation_evidence("W-002760")
    prediction = bundle["prediction"]
    assert "cost_overrun_probability_calibrated" not in prediction
    assert prediction["calibrated_probability_used_as_serving_evidence"] is False
    assert prediction["cost_overrun_serving_score"] is not None
    assert prediction["cost_overrun_serving_percentile_0_100"] is not None
    assert prediction["delay_model"]["available"] is False
    assert bundle["governance"]["detector_hotspots_used"] is False
    assert "detector_hotspots" not in json.dumps(bundle["trend"])


def test_direct_guideline_references_resolve(day8_repository, day8_retriever):
    bundle = day8_repository.build_explanation_evidence("W-001937")
    known = {row["chunk_id"] for row in day8_retriever.chunks}
    direct = set(bundle["compliance"]["direct_chunk_ids"])
    assert direct
    assert direct.issubset(known)


def test_no_evaluation_or_helper_artifact_enters_bundle(day8_repository):
    bundle = day8_repository.build_explanation_evidence("W-001937")
    serialized = json.dumps(bundle).casefold()
    for prohibited in ("ground_truth", "injected_anomaly", "expected_risk"):
        assert prohibited not in serialized
    assert bundle["governance"]["evaluation_or_helper_artifacts_used"] is False
