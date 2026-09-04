"""Generate governed Day-6 predictive modelling and current-score artifacts."""

from __future__ import annotations

from datetime import date
import importlib.metadata
import json
from pathlib import Path
import platform
from typing import Any

import joblib
import numpy as np
import pandas as pd

from intelligence.data.config import load_settings
from intelligence.data.loader import load_operational_data
from intelligence.data.paths import ProjectPaths

from .delay import delay_feasibility, delay_training_rows, train_delay_models
from .explain import build_shap_explanations
from .feature_sets import (
    ABSOLUTE_DATE_FIELDS,
    COST_OVERRUN_PREDICTORS,
    DELAY_PREDICTORS,
    OUTCOME_OR_RECONCILIATION_FIELDS,
)
from .modeling import (
    RANDOM_FOREST_PARAMETERS,
    XGBOOST_PARAMETERS,
    TrainedTargetModels,
    binary_metrics,
    predict_target_models,
)
from .overrun import (
    cost_overrun_feasibility,
    cost_overrun_training_rows,
    train_cost_overrun_models,
)
from .snapshot_builder import LANDMARK_FRACTIONS, build_historical_landmark_snapshots
from .splitting import attach_split, make_work_level_split, split_metadata
from .targets import COST_OVERRUN_TARGET, DELAY_TARGET
from .serving import (
    CALIBRATION_SERVING_ELIGIBLE,
    CALIBRATION_SERVING_REASON,
    CALIBRATION_STATUS,
    COST_MODEL_QUALITY_STATUS,
    COST_SERVING_STATUS,
    DELAY_MODEL_QUALITY_STATUS,
    DELAY_SERVING_STATUS,
    SERVING_PERCENTILE_FIELD,
    SERVING_POLICY,
    SERVING_RANK_FIELD,
    SERVING_SCORE_FIELD,
    SERVING_SCORE_SOURCE_FIELD,
    SHAP_MODEL_OUTPUT,
    apply_cost_overrun_serving_contract,
)


MODEL_STATUS_INSUFFICIENT = "INSUFFICIENT_SUPERVISED_OUTCOME_DATA"
CURRENT_STAGE_NOT_APPLICABLE = "NOT_APPLICABLE_STAGE"
CURRENT_OUTCOME_KNOWN = "OUTCOME_ALREADY_KNOWN"
CURRENT_PREDICTION_ELIGIBLE = "PREDICTED_EARLY_WARNING_ELIGIBLE"
CURRENT_OBSERVED_OVERDUE = "OBSERVED_OVERDUE"
CURRENT_OBSERVED_OVER_SANCTION = "OBSERVED_OVER_SANCTION"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _probability_distribution(values: pd.Series) -> dict[str, float] | None:
    clean = values.dropna().astype("float64")
    if clean.empty:
        return None
    return {
        "minimum": float(clean.min()),
        "p25": float(clean.quantile(0.25)),
        "median": float(clean.median()),
        "p75": float(clean.quantile(0.75)),
        "maximum": float(clean.max()),
        "mean": float(clean.mean()),
    }


def _percentile_0_100(values: pd.Series) -> pd.Series:
    result = pd.Series(np.nan, index=values.index, dtype="float64")
    clean = values.dropna()
    if clean.empty:
        return result
    if len(clean) == 1:
        result.loc[clean.index] = 100.0
    else:
        ranks = clean.rank(method="average", ascending=True)
        result.loc[clean.index] = (ranks - 1.0) / (len(clean) - 1.0) * 100.0
    return result


def _evaluate_target(
    trained: TrainedTargetModels,
    assigned_rows: pd.DataFrame,
) -> tuple[dict[str, Any], pd.DataFrame]:
    test = assigned_rows.loc[assigned_rows["split"].eq("TEST")].copy()
    validation = assigned_rows.loc[assigned_rows["split"].eq("VALIDATION")].copy()
    test_predictions = predict_target_models(trained, test)
    validation_predictions = predict_target_models(trained, validation)
    test = pd.concat([test, test_predictions], axis=1)
    validation = pd.concat([validation, validation_predictions], axis=1)

    landmarks: dict[str, Any] = {}
    for fraction in LANDMARK_FRACTIONS:
        group = test.loc[test["landmark_fraction"].eq(fraction)]
        key = f"{int(fraction * 100)}_percent"
        landmarks[key] = {
            "test_work_count": int(group["work_id"].nunique()),
            "positive_prevalence": float(group[trained.target].mean()) if len(group) else None,
            "xgboost_uncalibrated": binary_metrics(
                group[trained.target], group["xgb_probability_uncalibrated"]
            ),
            "xgboost_calibrated": binary_metrics(
                group[trained.target], group["xgb_probability_calibrated"]
            ),
            "random_forest_baseline": binary_metrics(
                group[trained.target], group["rf_probability"]
            ),
        }

    metrics = {
        "status": "EVALUATED",
        "primary_model": "XGBoost",
        "baseline_model": "RandomForestClassifier",
        "primary_prototype_landmark": "50_percent",
        "test_set_used_for_tuning": False,
        "landmarks": landmarks,
        "overall_repeated_row_diagnostic": {
            "warning": "Each work can appear at multiple landmarks; this is secondary only.",
            "xgboost_uncalibrated": binary_metrics(
                test[trained.target], test["xgb_probability_uncalibrated"]
            ),
            "xgboost_calibrated": binary_metrics(
                test[trained.target], test["xgb_probability_calibrated"]
            ),
            "random_forest_baseline": binary_metrics(
                test[trained.target], test["rf_probability"]
            ),
        },
        "calibration": {
            "method": "sigmoid_platt_on_xgboost_log_odds",
            "fit_partition": "VALIDATION_ONLY",
            "validation_uncalibrated": binary_metrics(
                validation[trained.target], validation["xgb_probability_uncalibrated"]
            ),
            "validation_calibrated": binary_metrics(
                validation[trained.target], validation["xgb_probability_calibrated"]
            ),
            "test_uncalibrated": binary_metrics(
                test[trained.target], test["xgb_probability_uncalibrated"]
            ),
            "test_calibrated": binary_metrics(
                test[trained.target], test["xgb_probability_calibrated"]
            ),
        },
    }
    prediction_output = pd.DataFrame(
        {
            "prediction_target": trained.target,
            "work_id": test["work_id"],
            "landmark_fraction": test["landmark_fraction"],
            "true_outcome": test[trained.target],
            "xgb_probability_uncalibrated": test["xgb_probability_uncalibrated"],
            "xgb_probability_calibrated": test["xgb_probability_calibrated"],
            "rf_probability": test["rf_probability"],
        }
    )
    return metrics, prediction_output


def prepare_current_scoring_rows(
    project_features: pd.DataFrame,
    predictors: tuple[str, ...],
) -> pd.DataFrame:
    """Map the frozen runtime snapshot to the historical predictor contract."""

    missing = [name for name in predictors if name != "landmark_fraction" and name not in project_features]
    if missing:
        raise ValueError(f"Current feature snapshot lacks predictive fields: {missing}")
    rows = project_features.copy()
    rows["landmark_fraction"] = (
        pd.to_numeric(rows["schedule_elapsed_ratio_as_of"], errors="coerce")
        .clip(lower=0.0, upper=1.0)
    )
    return rows


def _build_current_scores(
    project_features: pd.DataFrame,
    models: dict[str, TrainedTargetModels],
    feasibility: dict[str, dict[str, Any]],
) -> tuple[pd.DataFrame, list[pd.DataFrame]]:
    scores = project_features[["work_id", "lifecycle_stage"]].copy()
    execution = scores["lifecycle_stage"].eq("EXECUTION")
    completion = scores["lifecycle_stage"].eq("COMPLETION")
    scores["already_overdue_as_of"] = execution & pd.to_numeric(
        project_features["overdue_days_as_of"], errors="coerce"
    ).gt(0)
    scores["already_over_sanction_as_of"] = execution & pd.to_numeric(
        project_features["expenditure_to_sanction_pct_as_of"], errors="coerce"
    ).gt(100.0)
    explanations: list[pd.DataFrame] = []

    target_specs = (
        (
            "delay",
            DELAY_TARGET,
            DELAY_PREDICTORS,
            "already_overdue_as_of",
            CURRENT_OBSERVED_OVERDUE,
        ),
        (
            "cost_overrun",
            COST_OVERRUN_TARGET,
            COST_OVERRUN_PREDICTORS,
            "already_over_sanction_as_of",
            CURRENT_OBSERVED_OVER_SANCTION,
        ),
    )
    for prefix, target, predictors, observed_column, observed_label in target_specs:
        applicability = pd.Series(CURRENT_STAGE_NOT_APPLICABLE, index=scores.index, dtype="string")
        applicability.loc[completion] = CURRENT_OUTCOME_KNOWN
        uncalibrated = pd.Series(np.nan, index=scores.index, dtype="float64")
        calibrated = pd.Series(np.nan, index=scores.index, dtype="float64")
        if feasibility[target]["status"] == "FEASIBLE":
            applicability.loc[execution] = CURRENT_PREDICTION_ELIGIBLE
            applicability.loc[execution & scores[observed_column]] = observed_label
            current_rows = prepare_current_scoring_rows(project_features.loc[execution], predictors)
            predicted = predict_target_models(models[target], current_rows)
            uncalibrated.loc[execution] = predicted["xgb_probability_uncalibrated"].to_numpy()
            calibrated.loc[execution] = predicted["xgb_probability_calibrated"].to_numpy()
            explanations.append(
                build_shap_explanations(
                    models[target],
                    current_rows,
                    predicted["xgb_probability_uncalibrated"].to_numpy(),
                    predicted["xgb_probability_calibrated"].to_numpy(),
                    prediction_target=target,
                )
            )
        else:
            applicability.loc[execution] = MODEL_STATUS_INSUFFICIENT

        percentile_source = (
            uncalibrated.loc[execution]
            if target == COST_OVERRUN_TARGET
            else calibrated.loc[execution]
        )
        percentile = _percentile_0_100(percentile_source)
        scores[f"{prefix}_prediction_applicability"] = applicability
        scores[f"{prefix}_probability_uncalibrated"] = uncalibrated
        scores[f"{prefix}_probability_calibrated"] = calibrated
        scores[f"{prefix}_prediction_percentile_0_100"] = percentile.reindex(scores.index)
        scores[f"{prefix}_percentile_within_applicable_execution"] = percentile.reindex(
            scores.index
        )

    ordered = [
        "work_id",
        "lifecycle_stage",
        "delay_prediction_applicability",
        "already_overdue_as_of",
        "delay_probability_uncalibrated",
        "delay_probability_calibrated",
        "delay_prediction_percentile_0_100",
        "delay_percentile_within_applicable_execution",
        "cost_overrun_prediction_applicability",
        "already_over_sanction_as_of",
        "cost_overrun_probability_uncalibrated",
        "cost_overrun_probability_calibrated",
        "cost_overrun_prediction_percentile_0_100",
        "cost_overrun_percentile_within_applicable_execution",
    ]
    return apply_cost_overrun_serving_contract(scores[ordered]), explanations


def _model_metadata(
    target: str,
    features: tuple[str, ...],
    feasibility: dict[str, Any],
    assigned_rows: pd.DataFrame | None,
    trained: TrainedTargetModels | None,
    artifact_paths: dict[str, str | None],
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "target_definition": (
            "completion_date > expected_completion_date"
            if target == DELAY_TARGET
            else "visible final_expenditure_inr > sanctioned_amount_inr"
        ),
        "status": feasibility["status"],
        "training_snapshot_policy": (
            "25/50/75 percent of planned execution; sanction visible; outcome unknown; "
            "payments/progress/actual start restricted to landmark time"
        ),
        "landmark_fractions": list(LANDMARK_FRACTIONS),
        **feasibility,
        "feature_list": list(features),
        "excluded_leakage_fields": sorted(
            ABSOLUTE_DATE_FIELDS | OUTCOME_OR_RECONCILIATION_FIELDS
        ),
        "random_state": 42,
        "ground_truth_used": False,
        "duplicate_helper_used": False,
        "known_synthetic_completion_date_artifact": True,
        "artifacts": artifact_paths,
    }
    if target == DELAY_TARGET:
        metadata.update(
            {
                "model_quality_status": DELAY_MODEL_QUALITY_STATUS,
                "serving_status": DELAY_SERVING_STATUS,
                "serving_score_field": None,
            }
        )
    else:
        metadata.update(
            {
                "calibration_status": CALIBRATION_STATUS,
                "calibration_serving_eligible": CALIBRATION_SERVING_ELIGIBLE,
                "calibration_serving_reason": CALIBRATION_SERVING_REASON,
                "model_quality_status": COST_MODEL_QUALITY_STATUS,
                "serving_status": COST_SERVING_STATUS,
                "serving_policy": SERVING_POLICY,
                "serving_score_field": SERVING_SCORE_FIELD,
                "serving_score_source_field": SERVING_SCORE_SOURCE_FIELD,
                "serving_percentile_field": SERVING_PERCENTILE_FIELD,
                "serving_rank_field": SERVING_RANK_FIELD,
                "shap_model_output_explained": SHAP_MODEL_OUTPUT,
            }
        )
    if trained is None or assigned_rows is None:
        metadata.update(
            {
                "reason_not_fitted": MODEL_STATUS_INSUFFICIENT,
                "imputation_values": None,
                "split": None,
                "xgboost_parameters": None,
                "random_forest_parameters": None,
                "calibration_method": None,
            }
        )
        return metadata

    imputation_values = {
        feature: float(value)
        for feature, value in zip(features, trained.imputer.statistics_, strict=True)
    }
    metadata.update(
        {
            "training_row_count": int(len(assigned_rows)),
            "imputation_values": imputation_values,
            "imputer_fit_partition": "TRAIN_ONLY",
            "imputer_fit_work_ids": list(trained.imputer_fit_work_ids),
            "split": split_metadata(trained.split),
            "xgboost_parameters": {
                **XGBOOST_PARAMETERS,
                "scale_pos_weight": trained.scale_pos_weight,
            },
            "random_forest_parameters": RANDOM_FOREST_PARAMETERS,
            "calibration_method": "sigmoid_platt_on_xgboost_log_odds",
            "calibration_fit_partition": "VALIDATION_ONLY",
            "calibration_fit_work_ids": list(trained.calibrator.fit_work_ids),
            "calibration_parameters": {
                "coefficient": float(trained.calibrator.model.coef_[0, 0]),
                "intercept": float(trained.calibrator.model.intercept_[0]),
            },
            "test_set_used_for_tuning": False,
        }
    )
    return metadata


def run_day6(
    paths: ProjectPaths,
    as_of_date: date,
) -> dict[str, Any]:
    bundle = load_operational_data(paths)
    snapshots = build_historical_landmark_snapshots(bundle, as_of_date)
    delay_rows = delay_training_rows(snapshots)
    cost_rows = cost_overrun_training_rows(snapshots)
    feasibility = {
        DELAY_TARGET: delay_feasibility(delay_rows),
        COST_OVERRUN_TARGET: cost_overrun_feasibility(cost_rows),
    }

    modeling_dir = paths.processed_data_dir / "modeling" / "day6"
    evaluation_dir = paths.processed_data_dir / "evaluation"
    predictive_model_dir = paths.models_dir / "predictive"
    for directory in (modeling_dir, evaluation_dir, predictive_model_dir):
        directory.mkdir(parents=True, exist_ok=True)

    snapshots.to_csv(
        modeling_dir / "predictive_landmark_snapshots.csv",
        index=False,
        date_format="%Y-%m-%dT%H:%M:%S",
    )
    models: dict[str, TrainedTargetModels] = {}
    assigned: dict[str, pd.DataFrame | None] = {}
    training_rows = {DELAY_TARGET: delay_rows, COST_OVERRUN_TARGET: cost_rows}
    trainers = {
        DELAY_TARGET: train_delay_models,
        COST_OVERRUN_TARGET: train_cost_overrun_models,
    }
    output_names = {
        DELAY_TARGET: "delay_training_rows.csv",
        COST_OVERRUN_TARGET: "cost_overrun_training_rows.csv",
    }
    test_prediction_outputs: list[pd.DataFrame] = []
    metrics: dict[str, Any] = {
        "as_of_date": as_of_date.isoformat(),
        "test_set_policy": "Viewed only after feature lists, parameters, and calibration policy were fixed.",
    }

    for target, rows in training_rows.items():
        if feasibility[target]["status"] == "FEASIBLE":
            split = make_work_level_split(rows, target)
            assigned_rows = attach_split(rows, split)
            trained = trainers[target](assigned_rows, split)
            models[target] = trained
            assigned[target] = assigned_rows
            target_metrics, test_predictions = _evaluate_target(trained, assigned_rows)
            metrics[target] = target_metrics
            test_prediction_outputs.append(test_predictions)
            assigned_rows.to_csv(
                modeling_dir / output_names[target],
                index=False,
                date_format="%Y-%m-%dT%H:%M:%S",
            )
        else:
            insufficient = rows.copy()
            insufficient["split"] = "NOT_SPLIT_INSUFFICIENT_SUPERVISED_OUTCOME_DATA"
            insufficient.to_csv(
                modeling_dir / output_names[target],
                index=False,
                date_format="%Y-%m-%dT%H:%M:%S",
            )
            assigned[target] = None
            metrics[target] = {
                "status": MODEL_STATUS_INSUFFICIENT,
                "feasibility": feasibility[target],
                "test_metrics": None,
            }

    artifact_paths_by_target: dict[str, dict[str, str | None]] = {}
    for target, stem in ((DELAY_TARGET, "delay"), (COST_OVERRUN_TARGET, "cost_overrun")):
        if target not in models:
            artifact_paths_by_target[target] = {
                "xgboost": None,
                "random_forest": None,
                "calibrator": None,
                "imputer": None,
            }
            continue
        trained = models[target]
        paths_for_target = {
            "xgboost": predictive_model_dir / f"{stem}_xgboost.joblib",
            "random_forest": predictive_model_dir / f"{stem}_random_forest.joblib",
            "calibrator": predictive_model_dir / f"{stem}_calibrator.joblib",
            "imputer": predictive_model_dir / f"{stem}_imputer.joblib",
        }
        joblib.dump(trained.xgboost, paths_for_target["xgboost"])
        joblib.dump(trained.random_forest, paths_for_target["random_forest"])
        joblib.dump(trained.calibrator, paths_for_target["calibrator"])
        joblib.dump(trained.imputer, paths_for_target["imputer"])
        artifact_paths_by_target[target] = {
            name: str(path.relative_to(paths.project_root)).replace("\\", "/")
            for name, path in paths_for_target.items()
        }

    project_features = pd.read_csv(
        paths.processed_data_dir / "project_features.csv", low_memory=False
    )
    predictive_scores, explanation_parts = _build_current_scores(
        project_features, models, feasibility
    )
    predictive_scores_path = paths.processed_data_dir / "predictive_scores.csv"
    predictive_scores.to_csv(predictive_scores_path, index=False)
    explanations = (
        pd.concat(explanation_parts, ignore_index=True)
        if explanation_parts
        else pd.DataFrame(
            columns=["work_id", "prediction_target", "explanation_scope"]
        )
    )
    explanations_path = paths.processed_data_dir / "predictive_explanations.csv"
    explanations.to_csv(explanations_path, index=False)

    metrics_path = evaluation_dir / "day6_predictive_metrics.json"
    _write_json(metrics_path, metrics)
    test_predictions = (
        pd.concat(test_prediction_outputs, ignore_index=True)
        if test_prediction_outputs
        else pd.DataFrame(
            columns=["prediction_target", "work_id", "landmark_fraction", "true_outcome"]
        )
    )
    test_predictions.to_csv(evaluation_dir / "day6_test_predictions.csv", index=False)

    library_versions = {
        name: importlib.metadata.version(name)
        for name in ("numpy", "pandas", "scikit-learn", "xgboost", "shap", "joblib")
    }
    metadata = {
        "as_of_date": as_of_date.isoformat(),
        "python_version": platform.python_version(),
        "library_versions": library_versions,
        "ground_truth_used": False,
        "duplicate_helper_used": False,
        "known_synthetic_completion_date_artifact": True,
        "targets": {
            DELAY_TARGET: _model_metadata(
                DELAY_TARGET,
                DELAY_PREDICTORS,
                feasibility[DELAY_TARGET],
                assigned[DELAY_TARGET],
                models.get(DELAY_TARGET),
                artifact_paths_by_target[DELAY_TARGET],
            ),
            COST_OVERRUN_TARGET: _model_metadata(
                COST_OVERRUN_TARGET,
                COST_OVERRUN_PREDICTORS,
                feasibility[COST_OVERRUN_TARGET],
                assigned[COST_OVERRUN_TARGET],
                models.get(COST_OVERRUN_TARGET),
                artifact_paths_by_target[COST_OVERRUN_TARGET],
            ),
        },
    }
    metadata_path = predictive_model_dir / "predictive_model_metadata.json"
    _write_json(metadata_path, metadata)

    execution = predictive_scores["lifecycle_stage"].eq("EXECUTION")
    summary = {
        "as_of_date": as_of_date.isoformat(),
        "delay_model_feasibility": feasibility[DELAY_TARGET],
        "cost_overrun_model_feasibility": feasibility[COST_OVERRUN_TARGET],
        "landmark_counts": {
            str(key): int(value)
            for key, value in snapshots["landmark_fraction"].value_counts().sort_index().items()
        },
        "current_execution_work_count": int(execution.sum()),
        "current_execution_works_with_delay_probability": int(
            predictive_scores.loc[execution, "delay_probability_calibrated"].notna().sum()
        ),
        "current_execution_works_with_cost_overrun_probability": int(
            predictive_scores.loc[execution, "cost_overrun_probability_calibrated"].notna().sum()
        ),
        "current_observed_overdue_count": int(
            predictive_scores["already_overdue_as_of"].sum()
        ),
        "current_observed_over_sanction_count": int(
            predictive_scores["already_over_sanction_as_of"].sum()
        ),
        "current_probability_distributions": {
            "delay": _probability_distribution(
                predictive_scores.loc[execution, "delay_probability_calibrated"]
            ),
            "cost_overrun_raw_serving": _probability_distribution(
                predictive_scores.loc[execution, SERVING_SCORE_FIELD]
            ),
            "cost_overrun_calibrated_diagnostic": _probability_distribution(
                predictive_scores.loc[execution, "cost_overrun_probability_calibrated"]
            ),
        },
        "delay_serving_status": DELAY_SERVING_STATUS,
        "cost_overrun_serving_status": COST_SERVING_STATUS,
        "cost_overrun_calibration_status": CALIBRATION_STATUS,
        "cost_overrun_calibration_serving_eligible": CALIBRATION_SERVING_ELIGIBLE,
        "cost_overrun_model_quality_status": COST_MODEL_QUALITY_STATUS,
        "serving_score_field": SERVING_SCORE_FIELD,
        "serving_score_source_field": SERVING_SCORE_SOURCE_FIELD,
        "serving_percentile_field": SERVING_PERCENTILE_FIELD,
        "serving_rank_field": SERVING_RANK_FIELD,
        "artifacts": {
            "predictive_landmark_snapshots": "data/processed/modeling/day6/predictive_landmark_snapshots.csv",
            "delay_training_rows": "data/processed/modeling/day6/delay_training_rows.csv",
            "cost_overrun_training_rows": "data/processed/modeling/day6/cost_overrun_training_rows.csv",
            "predictive_scores": "data/processed/predictive_scores.csv",
            "predictive_explanations": "data/processed/predictive_explanations.csv",
            "metrics": "data/processed/evaluation/day6_predictive_metrics.json",
            "test_predictions": "data/processed/evaluation/day6_test_predictions.csv",
            "model_metadata": "code/models/predictive/predictive_model_metadata.json",
        },
        "final_fused_risk_created": False,
    }
    summary_path = paths.processed_data_dir / "day6_predictive_summary.json"
    _write_json(summary_path, summary)
    return {
        "summary": summary,
        "metrics": metrics,
        "metadata": metadata,
        "predictive_scores": predictive_scores,
        "predictive_explanations": explanations,
    }


def main() -> int:
    paths = ProjectPaths.discover()
    settings = load_settings(paths)
    result = run_day6(paths, settings.as_of_date)
    print(json.dumps(_json_safe(result["summary"]), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
