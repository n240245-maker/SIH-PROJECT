"""Day-6.1 serving-orientation and frozen-evaluation safety tests."""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import numpy as np
import pandas as pd

from intelligence.predictive import serving_audit
from intelligence.predictive.serving import (
    CALIBRATION_STATUS,
    COST_MODEL_QUALITY_STATUS,
    DELAY_MODEL_QUALITY_STATUS,
    SERVING_PERCENTILE_FIELD,
    SERVING_RANK_FIELD,
    SERVING_SCORE_FIELD,
    SERVING_SCORE_SOURCE_FIELD,
    SHAP_MODEL_OUTPUT,
)


FROZEN_DAY6_HASHES = dict(serving_audit.FROZEN_DAY6_HASHES)
EXPECTED_SPLIT_HASHES = {
    "train_work_ids_sha256": "62829FF8E8D3B82EAFCA3E7EED2C182E2153F6ED94A93D7C7EBB700E7C92CE09",
    "validation_work_ids_sha256": "BEFB01721ADE7CC2CF4397587489057A734386E90F34A8A9EBCE860DFBA6B3F2",
    "test_work_ids_sha256": "2ACFBEB50FC3A038B270FE48D141F25A46E715739BAD19D1D2D35E71B0B87933",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def test_negative_calibration_is_retained_but_non_serving(project_paths):
    metadata = json.loads(
        (
            project_paths.models_dir
            / "predictive"
            / "predictive_model_metadata.json"
        ).read_text(encoding="utf-8")
    )
    cost = metadata["targets"]["cost_overrun_outcome"]
    assert cost["calibration_parameters"]["coefficient"] == -0.4646330588869883
    assert cost["calibration_status"] == CALIBRATION_STATUS == "UNSTABLE_RANK_REVERSAL"
    assert cost["calibration_serving_eligible"] is False
    assert "diagnostic audit" in cost["calibration_serving_reason"]
    assert cost["model_quality_status"] == COST_MODEL_QUALITY_STATUS
    assert cost["serving_score_field"] == SERVING_SCORE_FIELD
    assert metadata["day6_1_serving_safety_audit"]["models_retrained"] is False
    assert metadata["day6_1_serving_safety_audit"]["models_retuned"] is False


def test_raw_probability_controls_serving_score_percentile_and_rank(project_paths):
    scores = pd.read_csv(project_paths.processed_data_dir / "predictive_scores.csv")
    execution = scores.loc[scores["lifecycle_stage"].eq("EXECUTION")].copy()
    assert len(scores) == scores["work_id"].nunique() == 3_000
    np.testing.assert_allclose(
        execution[SERVING_SCORE_FIELD],
        execution[SERVING_SCORE_SOURCE_FIELD],
        rtol=0,
        atol=0,
    )
    assert execution[SERVING_PERCENTILE_FIELD].between(0, 100).all()
    assert execution["cost_overrun_calibration_serving_eligible"].eq(False).all()
    assert execution["cost_overrun_probability_calibrated"].notna().all()

    expected = execution.sort_values(
        [SERVING_SCORE_SOURCE_FIELD, "work_id"],
        ascending=[False, True],
        kind="stable",
    )
    assert expected[SERVING_RANK_FIELD].tolist() == list(range(1, len(expected) + 1))
    assert expected[SERVING_PERCENTILE_FIELD].is_monotonic_decreasing
    assert expected[SERVING_SCORE_FIELD].is_monotonic_decreasing
    np.testing.assert_allclose(
        execution["cost_overrun_prediction_percentile_0_100"],
        execution[SERVING_PERCENTILE_FIELD],
    )
    assert not np.allclose(
        execution[SERVING_SCORE_FIELD],
        execution["cost_overrun_probability_calibrated"],
    )


def test_shap_and_serving_refer_to_the_same_raw_xgboost_model(project_paths):
    scores = pd.read_csv(project_paths.processed_data_dir / "predictive_scores.csv")
    explanations = pd.read_csv(
        project_paths.processed_data_dir / "predictive_explanations.csv"
    )
    aligned = explanations.merge(
        scores[["work_id", SERVING_SCORE_FIELD]],
        on="work_id",
        how="left",
        validate="one_to_one",
    )
    assert len(aligned) == 801
    np.testing.assert_allclose(
        aligned["raw_model_probability"], aligned[SERVING_SCORE_FIELD]
    )
    assert aligned["model_output_explained"].eq(SHAP_MODEL_OUTPUT).all()
    assert aligned["serving_score_field"].eq(SERVING_SCORE_FIELD).all()
    assert aligned["calibrated_probability_role"].eq(
        "DIAGNOSTIC_AUDIT_ONLY_NOT_EXPLAINED_BY_SHAP"
    ).all()
    assert aligned["calibrated_probability"].notna().all()


def test_delay_remains_unavailable_without_fabricated_probability(project_paths):
    scores = pd.read_csv(project_paths.processed_data_dir / "predictive_scores.csv")
    execution = scores["lifecycle_stage"].eq("EXECUTION")
    assert scores.loc[execution, "delay_prediction_applicability"].eq(
        "INSUFFICIENT_SUPERVISED_OUTCOME_DATA"
    ).all()
    assert scores.loc[execution, "delay_probability_uncalibrated"].isna().all()
    assert scores.loc[execution, "delay_probability_calibrated"].isna().all()
    metadata = json.loads(
        (
            project_paths.models_dir
            / "predictive"
            / "predictive_model_metadata.json"
        ).read_text(encoding="utf-8")
    )["targets"]["delay_outcome"]
    assert metadata["model_quality_status"] == DELAY_MODEL_QUALITY_STATUS
    assert metadata["serving_score_field"] is None


def test_summary_exposes_serving_governance(project_paths):
    summary = json.loads(
        (
            project_paths.processed_data_dir / "day6_predictive_summary.json"
        ).read_text(encoding="utf-8")
    )
    assert summary["delay_serving_status"] == DELAY_MODEL_QUALITY_STATUS
    assert summary["cost_overrun_calibration_status"] == CALIBRATION_STATUS
    assert summary["cost_overrun_calibration_serving_eligible"] is False
    assert summary["cost_overrun_model_quality_status"] == COST_MODEL_QUALITY_STATUS
    assert summary["serving_score_field"] == SERVING_SCORE_FIELD
    assert summary["serving_percentile_field"] == SERVING_PERCENTILE_FIELD
    assert summary["models_retrained_for_day6_1"] is False
    assert summary["models_retuned_for_day6_1"] is False
    distributions = summary["current_probability_distributions"]
    assert "cost_overrun_raw_serving" in distributions
    assert "cost_overrun_calibrated_diagnostic" in distributions


def test_day6_models_evaluation_training_rows_and_partitions_are_frozen(project_paths):
    for relative, expected in FROZEN_DAY6_HASHES.items():
        assert _sha256(project_paths.project_root / relative) == expected
    metadata = json.loads(
        (
            project_paths.models_dir
            / "predictive"
            / "predictive_model_metadata.json"
        ).read_text(encoding="utf-8")
    )
    split = metadata["targets"]["cost_overrun_outcome"]["split"]
    for field, expected in EXPECTED_SPLIT_HASHES.items():
        assert split[field] == expected


def test_serving_audit_has_no_training_or_evaluation_label_access():
    source = inspect.getsource(serving_audit).casefold()
    assert ".fit(" not in source
    assert "xgbclassifier" not in source
    assert "randomforestclassifier" not in source
    assert "load_evaluation_ground_truth" not in source
    assert "07_anomaly_ground_truth" not in source
    assert "duplicate_group_reference" not in source
