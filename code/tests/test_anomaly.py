"""Day-3 lifecycle anomaly, peer evidence, and evaluation-firewall tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from intelligence.anomaly.evaluation import evaluate_production_scores
from intelligence.anomaly.feature_selection import select_lifecycle_feature_sets
from intelligence.anomaly.isolation import numeric_feature_matrix
from intelligence.anomaly.peer_benchmark import (
    MINIMUM_PEER_GROUP_SIZE,
    robust_deviation,
)
from intelligence.anomaly.runner import ProductionArtifacts


EXPECTED_PROJECT_FEATURE_HASH = (
    "760D1D1366316C54CF928C5CCE03AD3A10F2793C0F986782477F03F6D9A77148"
)
PRODUCTION_MODULES = (
    "feature_selection.py",
    "peer_benchmark.py",
    "isolation.py",
    "scoring.py",
    "runner.py",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


@pytest.fixture(scope="module")
def governed_feature_inputs(project_paths):
    features = pd.read_csv(
        project_paths.processed_data_dir / "project_features.csv",
        encoding="utf-8",
        low_memory=False,
    )
    catalog = json.loads(
        (project_paths.processed_data_dir / "feature_catalog.json").read_text(
            encoding="utf-8"
        )
    )
    return features, catalog


@pytest.fixture(scope="module")
def feature_sets(governed_feature_inputs):
    features, catalog = governed_feature_inputs
    return select_lifecycle_feature_sets(features, catalog)


@pytest.fixture(scope="module")
def production_artifacts(project_paths):
    # Day 4 regression loads the frozen Day-3 artifacts; it must not retrain them.
    processed = project_paths.processed_data_dir
    model_directory = project_paths.models_dir / "anomaly"
    artifacts = ProductionArtifacts(
        anomaly_feature_sets=processed / "anomaly_feature_sets.json",
        peer_benchmark_evidence=processed / "peer_benchmark_evidence.csv",
        peer_benchmark_summary=processed / "peer_benchmark_summary.csv",
        anomaly_scores=processed / "anomaly_scores.csv",
        anomaly_evidence=processed / "anomaly_evidence.csv",
        anomaly_summary=processed / "anomaly_summary.json",
        model_metadata=model_directory / "anomaly_model_metadata.json",
        model_artifacts={
            "PRE_SANCTION": model_directory / "isolation_forest_pre_sanction.joblib",
            "EXECUTION": model_directory / "isolation_forest_execution.joblib",
            "COMPLETION": model_directory / "isolation_forest_completion.joblib",
        },
    )
    for path in (
        artifacts.anomaly_scores,
        artifacts.model_metadata,
        *artifacts.model_artifacts.values(),
    ):
        assert path.is_file()
    return artifacts


@pytest.fixture(scope="module")
def evaluation_artifacts(production_artifacts, project_paths):
    assert production_artifacts.anomaly_scores.is_file()
    return evaluate_production_scores(project_paths)


def test_feature_selection_starts_only_from_generic_pool(
    governed_feature_inputs, feature_sets
):
    _, catalog = governed_feature_inputs
    generic = {
        item["name"]
        for item in catalog["features"]
        if item["generic_anomaly_eligible"]
    }
    assert len(generic) == 32
    for details in feature_sets["stages"].values():
        assert set(details["selected_features"]) <= generic


def test_pre_sanction_uses_only_pre_sanction_cost_inputs(feature_sets):
    selected = feature_sets["stages"]["PRE_SANCTION"]["selected_features"]
    assert selected == [
        "recommended_amount_inr",
        "technical_estimate_amount_inr",
        "estimate_to_recommended_ratio",
    ]
    assert not any(
        token in name
        for name in selected
        for token in ("payment", "progress", "completion", "asset")
    )


def test_stage_local_variance_and_missingness_rules(feature_sets):
    completion_exclusions = {
        item["feature"]: item["reason"]
        for item in feature_sets["stages"]["COMPLETION"]["excluded_features"]
    }
    execution_exclusions = {
        item["feature"]: item["reason"]
        for item in feature_sets["stages"]["EXECUTION"]["excluded_features"]
    }
    assert completion_exclusions["latest_physical_progress_pct_as_of"] == (
        "ZERO_VARIANCE_WITHIN_STAGE"
    )
    assert completion_exclusions["overdue_days_as_of"] == (
        "EXCESSIVE_STAGE_MISSINGNESS"
    )
    assert execution_exclusions["actual_start_available_as_of"] == (
        "NEAR_ZERO_VARIANCE_WITHIN_STAGE"
    )


def test_three_independent_lifecycle_models_and_no_global_model(
    production_artifacts,
):
    metadata = json.loads(
        production_artifacts.model_metadata.read_text(encoding="utf-8")
    )
    models = {
        stage: joblib.load(path)
        for stage, path in production_artifacts.model_artifacts.items()
    }
    assert set(models) == {"PRE_SANCTION", "EXECUTION", "COMPLETION"}
    assert {model.lifecycle_stage for model in models.values()} == set(models)
    assert len({id(model.detector) for model in models.values()}) == 3
    assert metadata["model_count"] == 3
    assert metadata["global_model_used"] is False
    assert metadata["ground_truth_used_for_training"] is False


def test_median_imputation_is_fitted_within_each_stage(
    governed_feature_inputs, production_artifacts
):
    features, _ = governed_feature_inputs
    metadata = json.loads(
        production_artifacts.model_metadata.read_text(encoding="utf-8")
    )
    for stage, details in metadata["stages"].items():
        stage_rows = features.loc[features["lifecycle_stage"].eq(stage)]
        names = details["feature_list"]
        expected = numeric_feature_matrix(stage_rows, names).median()
        for name, value in details["imputation_values"].items():
            assert value == pytest.approx(float(expected[name]))


def test_peer_hierarchy_falls_back_and_respects_minimum(production_artifacts):
    evidence = pd.read_csv(production_artifacts.peer_benchmark_evidence)
    assert evidence["peer_group_size"].ge(MINIMUM_PEER_GROUP_SIZE).all()
    levels = set(evidence["peer_group_level"])
    assert "LEVEL_1_LIFECYCLE_STATE_SECTOR_SUB_SECTOR" in levels
    assert "LEVEL_2_LIFECYCLE_STATE_SECTOR" in levels
    assert any(not level.startswith("LEVEL_1") for level in levels)


def test_robust_deviation_mad_and_iqr_fallbacks_are_safe():
    mad_score, mad_method = robust_deviation(12.0, 10.0, 2.0, 5.0)
    iqr_score, iqr_method = robust_deviation(12.0, 10.0, 0.0, 4.0)
    constant_score, constant_method = robust_deviation(12.0, 10.0, 0.0, 0.0)
    assert mad_score == pytest.approx(0.6745)
    assert mad_method == "MODIFIED_Z_MAD"
    assert np.isfinite(iqr_score)
    assert iqr_method == "STANDARDIZED_IQR_FALLBACK"
    assert constant_score is None
    assert constant_method == "UNAVAILABLE_CONSTANT_PEER_DISTRIBUTION"


def test_anomaly_scores_have_governed_cardinality_and_ranking(
    production_artifacts,
):
    scores = pd.read_csv(production_artifacts.anomaly_scores)
    assert len(scores) == 3000
    assert scores["work_id"].nunique() == 3000
    assert scores["within_stage_anomaly_percentile_0_100"].between(0, 100).all()
    for _, stage in scores.groupby("lifecycle_stage"):
        most_unusual = stage.loc[stage["iforest_unusualness_score"].idxmax()]
        least_unusual = stage.loc[stage["iforest_unusualness_score"].idxmin()]
        assert most_unusual["within_stage_anomaly_percentile_0_100"] == pytest.approx(100)
        assert most_unusual["within_stage_rank"] == 1
        assert least_unusual["within_stage_anomaly_percentile_0_100"] == pytest.approx(0)


def test_no_probability_or_verdict_fields_are_created(production_artifacts):
    scores = pd.read_csv(production_artifacts.anomaly_scores, nrows=1)
    evidence = pd.read_csv(production_artifacts.anomaly_evidence, nrows=1)
    forbidden = ("fraud", "guilt", "risk_probability", "anomaly_probability")
    for name in [*scores.columns, *evidence.columns]:
        assert not any(term in name.lower() for term in forbidden)


def test_production_modules_have_no_evaluation_label_access(project_paths):
    module_directory = project_paths.project_root / "code" / "intelligence" / "anomaly"
    forbidden = (
        "load_evaluation_ground_truth",
        "07_anomaly_ground_truth",
        "injected_anomaly_",
        "expected_risk_",
        "duplicate_group_reference",
    )
    for filename in PRODUCTION_MODULES:
        source = (module_directory / filename).read_text(encoding="utf-8")
        assert not any(term in source for term in forbidden)


def test_evaluation_is_isolated_and_runs_after_production(
    evaluation_artifacts, production_artifacts
):
    metrics_path, scored_path = evaluation_artifacts
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert scored_path.parent.name == "evaluation"
    assert metrics["features_or_hyperparameters_changed_after_evaluation"] is False
    assert production_artifacts.anomaly_scores.parent.name == "processed"
    production_columns = pd.read_csv(
        production_artifacts.anomaly_scores, nrows=1
    ).columns
    assert "has_injected_anomaly" not in production_columns
    assert "injected_anomaly_count" not in production_columns


def test_project_feature_snapshot_is_unchanged(project_paths):
    feature_path = project_paths.processed_data_dir / "project_features.csv"
    assert _sha256(feature_path) == EXPECTED_PROJECT_FEATURE_HASH
