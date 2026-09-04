"""Day-6 leakage, splitting, model, scoring, and artifact guardrails."""

from __future__ import annotations

from datetime import date
import hashlib
import inspect
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier

from intelligence.features.aggregations import (
    aggregate_payments_as_of,
    aggregate_progress_as_of,
)
from intelligence.predictive import delay, overrun, snapshot_builder
from intelligence.predictive.feature_sets import (
    ABSOLUTE_DATE_FIELDS,
    COST_OVERRUN_PREDICTORS,
    DELAY_PREDICTORS,
    OUTCOME_OR_RECONCILIATION_FIELDS,
)
from intelligence.predictive.modeling import predict_target_models
from intelligence.predictive.runner import prepare_current_scoring_rows
from intelligence.predictive.splitting import attach_split, make_work_level_split
from intelligence.predictive.targets import (
    COST_OVERRUN_TARGET,
    DELAY_TARGET,
    build_completed_work_outcomes,
)


PRIOR_ARTIFACT_HASHES = {
    "data/processed/project_features.csv": "760D1D1366316C54CF928C5CCE03AD3A10F2793C0F986782477F03F6D9A77148",
    "data/processed/feature_catalog.json": "5A46220D8A7FE32491E10B7CC5FF783CCCC87592E009AFA7FD761D4B23059EB3",
    "data/processed/feature_quality_profile.json": "6DC6249CD79FA9C191C2D69528384507622C4820A7F099464AFFF9521CAAF1BD",
    "data/processed/anomaly_feature_sets.json": "7A62ED3017FBB810943F94BFA46918EBC839AC9F1F01C37A49F6E6E188CFC94C",
    "data/processed/peer_benchmark_evidence.csv": "9C22930D7B821CE1ACCC10EF7B41E93F8CE3ACEA03DC83D67E1D3243FB88E3D5",
    "data/processed/peer_benchmark_summary.csv": "EBD4DB143972483B95219F81FE0F55DEF0ABB0EC279C53016858E20E3E9F5F63",
    "data/processed/anomaly_scores.csv": "F65777B89067A8335AA953255C448774D7E52F08728B7455A4C9FBA7DF91D4CC",
    "data/processed/anomaly_evidence.csv": "F214411E58C3667CEC084C697F1E7D07CEBF85109B5FA935E05A4F480BB212A7",
    "data/processed/anomaly_summary.json": "7B3ADF407FAD315FD5F563375B6186DF30B10E6615D5D87FC9CFA59EA6FDA722",
    "data/processed/evaluation/anomaly_ground_truth_metrics.json": "7504817E4560B0ECAB1D85F181B0A9BA878829F23444C9936F5F84FE4111EE3C",
    "data/processed/evaluation/anomaly_ground_truth_scored.csv": "AD72DB39CF7C14E306BF1AE2C55A6730204903E4ACF766ADCD5382E488FB8381",
    "data/processed/duplicate_candidates.csv": "150EA1548FBC31C4B4FD67BF921BE8F5E95C720C5B269899032778F6F9203246",
    "data/processed/duplicate_summary.csv": "60950E8A0CC4250F43D70418281ACA8AFA9177E67C57434E551536C42224C3AA",
    "data/processed/duplicate_work_embeddings.npy": "C946D5A99D1D82230BD677CF1D6875F367770E37454091EDD6C48CC5D260C8BF",
    "data/processed/duplicate_work_embeddings_metadata.json": "15EBB520DAE1081F62AFE90D1F38A581C14BF4A9A852594EFF1CDE40BD9074F6",
    "data/processed/payment_irregularities.csv": "C7BCCF4DD02D6A6CDBF322E4B19AE393212B59898434B714C7D6868C2302BBE0",
    "data/processed/payment_irregularity_summary.csv": "7F3DEDFFD64C63E047113A5F616D2FA0016A16C7C72BE6081679C5DEB4BCDF7D",
    "data/processed/fund_progress_evidence.csv": "812D9295E38285CBAE784D2F6F3EBD606F7BED5981DD3279CF61975A3CFD206C",
    "data/processed/day4_detector_summary.json": "7ADABE3D1CEEBC8E2A022D1511E5A3C418B85A4B5FFCC63C7C9D64FA88884005",
    "data/processed/compliance_evidence.csv": "9ED912957A1260355DF50403950E0631C6896DF54A122E7749926FD443801C3D",
    "data/processed/compliance_summary.csv": "E3D5C37ABA64F494BBA4C93564FAD2A978241BA917530E5315851F28E237F69F",
    "data/processed/compliance_rule_registry.json": "55841F2468AECAB0FE4545932D343036ADCA4C999E3250672B1167F1F16DF6BE",
    "data/processed/guideline_chunks.json": "699933873A80B52F01D87AE7DF30C501A4116B3D7E71A03F19DF777C0CDABF77",
    "data/processed/guideline_manifest.json": "04789FB28A3C824949B9D4125D633B4DD45FE32A359F23A4D2A7DA3E2C10E2D0",
    "data/processed/day5_compliance_summary.json": "90DE98E39DA0B70BB2723BA65D37474EE596A93C0ED64CAF59D325E4FB64CC40",
    "code/models/anomaly/isolation_forest_pre_sanction.joblib": "A87EBECFA83E1DF9A52614FDCEAA038D7E7D87DEAEAF1231864CE3D1C6F54529",
    "code/models/anomaly/isolation_forest_execution.joblib": "C7267BD53FB0EEC426CE572FDBC6D17FBC9925A21485962FA20EFC3E47DEFFCD",
    "code/models/anomaly/isolation_forest_completion.joblib": "48C9C6AF5384C2C9CC19B55FD012A56CC73357F49611101FFF5A81250C78C86B",
    "code/models/anomaly/anomaly_model_metadata.json": "FA07C130E2BB37CA354922DE72F5872FA5DBE5F50FFF012A7919601E19349B1F",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


@pytest.fixture(scope="module")
def historical_snapshots(operational_bundle, snapshot_date):
    return snapshot_builder.build_historical_landmark_snapshots(
        operational_bundle, snapshot_date
    )


def test_landmarks_are_exact_and_outcome_is_unknown(
    historical_snapshots, operational_bundle, snapshot_date
):
    assert len(historical_snapshots) == 5_786
    assert not historical_snapshots["outcome_known_at_landmark"].any()
    works = operational_bundle.works.set_index("work_id")
    outcomes = build_completed_work_outcomes(
        operational_bundle, snapshot_date
    ).set_index("work_id")
    for row in historical_snapshots.itertuples(index=False):
        work = works.loc[row.work_id]
        expected = work["expected_start_date"] + (
            work["expected_completion_date"] - work["expected_start_date"]
        ) * row.landmark_fraction
        assert row.landmark_date == expected
        assert work["sanction_date"] <= row.landmark_date
        assert outcomes.loc[row.work_id, "completion_date"] > row.landmark_date


def test_historical_payment_progress_formulas_match_day2(
    historical_snapshots, operational_bundle
):
    row = historical_snapshots.loc[
        historical_snapshots["work_id"].eq("W-000001")
        & historical_snapshots["landmark_fraction"].eq(0.25)
    ].iloc[0]
    work_payments = operational_bundle.payments.loc[
        operational_bundle.payments["work_id"].eq(row["work_id"])
    ]
    work_progress = operational_bundle.progress.loc[
        operational_bundle.progress["work_id"].eq(row["work_id"])
    ]
    payment = aggregate_payments_as_of(work_payments, row["landmark_date"]).iloc[0]
    progress = aggregate_progress_as_of(work_progress, row["landmark_date"]).iloc[0]
    for field in (
        "released_payment_count_as_of",
        "released_payment_total_inr_as_of",
        "largest_payment_inr_as_of",
        "mean_payment_inr_as_of",
        "largest_payment_share_as_of",
        "days_since_last_payment_as_of",
    ):
        assert row[field] == pytest.approx(payment[field])
    for field in (
        "progress_report_count_as_of",
        "latest_physical_progress_pct_as_of",
        "latest_financial_progress_pct_as_of",
        "latest_expected_progress_pct_as_of",
        "physical_progress_decrease_count_as_of",
        "max_physical_progress_drop_pct_as_of",
        "physical_progress_velocity_pct_per_30d",
    ):
        if pd.isna(progress[field]):
            assert pd.isna(row[field])
        else:
            assert row[field] == pytest.approx(progress[field])
    assert int((work_payments["payment_release_date"] > row["landmark_date"]).sum()) > 0
    assert int((work_progress["report_date"] > row["landmark_date"]).sum()) > 0


def test_future_actual_start_and_forbidden_predictors_are_excluded(
    operational_bundle, historical_snapshots
):
    work = operational_bundle.works.iloc[0].astype("object").copy()
    landmark = snapshot_builder.derive_landmark_date(work, 0.25)
    work["actual_start_date"] = pd.Timestamp("2099-01-01")
    values = snapshot_builder._point_in_time_features(
        work,
        operational_bundle.payments.loc[
            operational_bundle.payments["work_id"].eq(work["work_id"])
        ],
        operational_bundle.progress.loc[
            operational_bundle.progress["work_id"].eq(work["work_id"])
        ],
        landmark,
        0.25,
    )
    assert values["actual_start_available_as_of"] is False
    assert pd.isna(values["days_since_actual_start_as_of"])
    for predictors in (DELAY_PREDICTORS, COST_OVERRUN_PREDICTORS):
        assert not set(predictors).intersection(ABSOLUTE_DATE_FIELDS)
        assert not set(predictors).intersection(OUTCOME_OR_RECONCILIATION_FIELDS)
        assert not any(name.startswith("source_current_") for name in predictors)
    assert "final_expenditure_inr" not in historical_snapshots
    assert "completion_date" not in historical_snapshots
    assert DELAY_PREDICTORS is not COST_OVERRUN_PREDICTORS


def test_operational_outcome_counts_and_feasibility(historical_snapshots):
    delay_rows = delay.delay_training_rows(historical_snapshots)
    cost_rows = overrun.cost_overrun_training_rows(historical_snapshots)
    assert delay.delay_feasibility(delay_rows) == {
        "status": "INSUFFICIENT_SUPERVISED_OUTCOME_DATA",
        "eligible_work_count": 1_929,
        "positive_work_count": 1_907,
        "negative_work_count": 22,
        "landmark_row_count": 5_786,
        "positive_prevalence": pytest.approx(1_907 / 1_929),
        "minimum_positive_work_count": 50,
        "minimum_negative_work_count": 50,
    }
    feasible = overrun.cost_overrun_feasibility(cost_rows)
    assert feasible["status"] == "FEASIBLE"
    assert feasible["eligible_work_count"] == 332
    assert feasible["positive_work_count"] == 210
    assert feasible["negative_work_count"] == 122
    assert feasible["landmark_row_count"] == 996


def test_work_level_split_is_deterministic_and_disjoint(historical_snapshots):
    rows = overrun.cost_overrun_training_rows(historical_snapshots)
    first = make_work_level_split(rows, COST_OVERRUN_TARGET)
    second = make_work_level_split(rows, COST_OVERRUN_TARGET)
    pd.testing.assert_frame_equal(first.assignments, second.assignments)
    assigned = attach_split(rows, first)
    assert assigned.groupby("work_id")["split"].nunique().eq(1).all()
    groups = [set(first.train_work_ids), set(first.validation_work_ids), set(first.test_work_ids)]
    assert not groups[0].intersection(groups[1] | groups[2])
    assert not groups[1].intersection(groups[2])
    assert [len(group) for group in groups] == [232, 50, 50]
    assert first.stratified


def test_model_artifacts_and_fit_partition_firewalls(project_paths):
    model_dir = project_paths.models_dir / "predictive"
    metadata = json.loads(
        (model_dir / "predictive_model_metadata.json").read_text(encoding="utf-8")
    )
    delay_metadata = metadata["targets"][DELAY_TARGET]
    cost_metadata = metadata["targets"][COST_OVERRUN_TARGET]
    assert delay_metadata["status"] == "INSUFFICIENT_SUPERVISED_OUTCOME_DATA"
    assert delay_metadata["artifacts"]["xgboost"] is None
    assert isinstance(joblib.load(model_dir / "cost_overrun_xgboost.joblib"), XGBClassifier)
    assert isinstance(
        joblib.load(model_dir / "cost_overrun_random_forest.joblib"),
        RandomForestClassifier,
    )
    split = cost_metadata["split"]
    train_ids = set(split["train_work_ids"])
    validation_ids = set(split["validation_work_ids"])
    test_ids = set(split["test_work_ids"])
    assert set(cost_metadata["imputer_fit_work_ids"]) == train_ids
    assert set(cost_metadata["calibration_fit_work_ids"]) == validation_ids
    assert test_ids.isdisjoint(train_ids | validation_ids)
    assert cost_metadata["test_set_used_for_tuning"] is False
    assert metadata["ground_truth_used"] is False
    assert metadata["duplicate_helper_used"] is False


def test_predictions_are_deterministic_and_bounded(project_paths):
    model_dir = project_paths.models_dir / "predictive"
    metadata = json.loads(
        (model_dir / "predictive_model_metadata.json").read_text(encoding="utf-8")
    )["targets"][COST_OVERRUN_TARGET]
    from intelligence.predictive.calibration import SigmoidProbabilityCalibrator
    from intelligence.predictive.modeling import TrainedTargetModels
    from intelligence.predictive.splitting import WorkLevelSplit

    dummy_split = WorkLevelSplit(pd.DataFrame(), (), (), (), True)
    trained = TrainedTargetModels(
        target=COST_OVERRUN_TARGET,
        features=tuple(metadata["feature_list"]),
        imputer=joblib.load(model_dir / "cost_overrun_imputer.joblib"),
        xgboost=joblib.load(model_dir / "cost_overrun_xgboost.joblib"),
        random_forest=joblib.load(model_dir / "cost_overrun_random_forest.joblib"),
        calibrator=joblib.load(model_dir / "cost_overrun_calibrator.joblib"),
        imputer_fit_work_ids=(),
        split=dummy_split,
        scale_pos_weight=float(metadata["xgboost_parameters"]["scale_pos_weight"]),
    )
    assert isinstance(trained.calibrator, SigmoidProbabilityCalibrator)
    current = pd.read_csv(project_paths.processed_data_dir / "project_features.csv")
    current = current.loc[current["lifecycle_stage"].eq("EXECUTION")].head(20)
    rows = prepare_current_scoring_rows(current, trained.features)
    first = predict_target_models(trained, rows)
    second = predict_target_models(trained, rows)
    pd.testing.assert_frame_equal(first, second)
    assert first.apply(lambda column: column.between(0, 1).all()).all()


def test_current_outputs_stage_observation_and_language(project_paths):
    processed = project_paths.processed_data_dir
    scores = pd.read_csv(processed / "predictive_scores.csv")
    explanations = pd.read_csv(processed / "predictive_explanations.csv")
    assert len(scores) == scores["work_id"].nunique() == 3_000
    assert scores.loc[scores["lifecycle_stage"].eq("PRE_SANCTION"), "cost_overrun_prediction_applicability"].eq(
        "NOT_APPLICABLE_STAGE"
    ).all()
    assert scores.loc[scores["lifecycle_stage"].eq("COMPLETION"), "cost_overrun_prediction_applicability"].eq(
        "OUTCOME_ALREADY_KNOWN"
    ).all()
    execution = scores["lifecycle_stage"].eq("EXECUTION")
    assert scores.loc[execution, "cost_overrun_probability_calibrated"].notna().all()
    assert scores.loc[execution, "delay_probability_calibrated"].isna().all()
    assert int(scores["already_overdue_as_of"].sum()) == 272
    assert int(scores["already_over_sanction_as_of"].sum()) == 20
    assert scores["cost_overrun_prediction_percentile_0_100"].dropna().between(0, 100).all()
    assert explanations["explanation_scope"].str.contains("non-causal", case=False).all()
    production_columns = " ".join(scores.columns).casefold()
    assert "fraud" not in production_columns
    assert "final_risk" not in production_columns
    assert DELAY_TARGET not in scores
    assert COST_OVERRUN_TARGET not in scores


def test_predictive_sources_do_not_load_evaluation_labels():
    modules = (snapshot_builder, delay, overrun)
    source = "\n".join(inspect.getsource(module) for module in modules).casefold()
    assert "load_evaluation_ground_truth" not in source
    assert "07_anomaly_ground_truth" not in source
    assert "fraud_probability" not in source


def test_all_prior_artifacts_remain_byte_identical(project_paths):
    for relative, expected in PRIOR_ARTIFACT_HASHES.items():
        assert _sha256(project_paths.project_root / relative) == expected
