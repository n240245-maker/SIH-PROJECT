"""Three independent lifecycle Isolation Forest detectors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import platform
from typing import Any, Mapping

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer


IFOREST_HYPERPARAMETERS: dict[str, Any] = {
    "n_estimators": 300,
    "max_samples": "auto",
    "contamination": "auto",
    "random_state": 42,
    "n_jobs": -1,
}

MODEL_FILENAMES = {
    "PRE_SANCTION": "isolation_forest_pre_sanction.joblib",
    "EXECUTION": "isolation_forest_execution.joblib",
    "COMPLETION": "isolation_forest_completion.joblib",
}


@dataclass(slots=True)
class LifecycleIsolationModel:
    """Persisted preprocessing and detector state for one lifecycle stage."""

    lifecycle_stage: str
    feature_names: list[str]
    imputer: SimpleImputer
    detector: IsolationForest


def numeric_feature_matrix(frame: pd.DataFrame, feature_names: list[str]) -> pd.DataFrame:
    """Convert governed numeric/boolean features without inventing domain zeros."""

    matrix = pd.DataFrame(index=frame.index)
    for name in feature_names:
        values = frame[name]
        if pd.api.types.is_bool_dtype(values.dtype):
            matrix[name] = values.astype("float64")
            continue
        if pd.api.types.is_object_dtype(values.dtype) or pd.api.types.is_string_dtype(values.dtype):
            lowered = values.dropna().astype(str).str.lower()
            if not lowered.empty and set(lowered.unique()).issubset({"true", "false"}):
                matrix[name] = values.map(
                    {True: 1.0, False: 0.0, "True": 1.0, "False": 0.0, "true": 1.0, "false": 0.0}
                )
                continue
        matrix[name] = pd.to_numeric(values, errors="raise").astype("float64")
    return matrix


def fit_lifecycle_model(
    stage_rows: pd.DataFrame,
    lifecycle_stage: str,
    feature_names: list[str],
) -> tuple[LifecycleIsolationModel, pd.DataFrame, dict[str, float]]:
    """Fit stage-local median preprocessing and one Isolation Forest."""

    if stage_rows.empty:
        raise ValueError(f"Cannot fit an empty lifecycle stage: {lifecycle_stage}")
    matrix = numeric_feature_matrix(stage_rows, feature_names)
    imputer = SimpleImputer(strategy="median")
    transformed = imputer.fit_transform(matrix)
    if transformed.shape != matrix.shape or np.isnan(transformed).any():
        raise ValueError(f"Median preprocessing failed for {lifecycle_stage}")

    detector = IsolationForest(**IFOREST_HYPERPARAMETERS)
    detector.fit(transformed)
    raw_score = detector.score_samples(transformed)
    unusualness = -raw_score
    population = len(stage_rows)
    unusual_series = pd.Series(unusualness, index=stage_rows.index)
    percentile_rank = unusual_series.rank(method="average", ascending=True)
    if population == 1:
        percentile = pd.Series(100.0, index=stage_rows.index)
    else:
        percentile = 100.0 * (percentile_rank - 1.0) / (population - 1.0)
    within_stage_rank = unusual_series.rank(
        method="first", ascending=False
    ).astype("int64")

    scores = pd.DataFrame(
        {
            "work_id": stage_rows["work_id"].to_numpy(),
            "lifecycle_stage": lifecycle_stage,
            "iforest_score_samples_raw": raw_score,
            "iforest_unusualness_score": unusualness,
            "within_stage_anomaly_percentile_0_100": percentile.to_numpy(),
            "within_stage_rank": within_stage_rank.to_numpy(),
            "stage_population": population,
        },
        index=stage_rows.index,
    )
    imputation_values = {
        name: float(value)
        for name, value in zip(feature_names, imputer.statistics_, strict=True)
    }
    return (
        LifecycleIsolationModel(lifecycle_stage, feature_names, imputer, detector),
        scores,
        imputation_values,
    )


def train_lifecycle_models(
    features: pd.DataFrame,
    feature_sets: Mapping[str, Any],
    *,
    feature_snapshot_date: str,
) -> tuple[dict[str, LifecycleIsolationModel], pd.DataFrame, dict[str, Any]]:
    """Train exactly one independent detector per lifecycle stage."""

    models: dict[str, LifecycleIsolationModel] = {}
    scores: list[pd.DataFrame] = []
    stage_metadata: dict[str, Any] = {}
    for lifecycle_stage in ("PRE_SANCTION", "EXECUTION", "COMPLETION"):
        stage_rows = features.loc[
            features["lifecycle_stage"].eq(lifecycle_stage)
        ].copy()
        selected = list(
            feature_sets["stages"][lifecycle_stage]["selected_features"]
        )
        model, stage_scores, medians = fit_lifecycle_model(
            stage_rows, lifecycle_stage, selected
        )
        models[lifecycle_stage] = model
        scores.append(stage_scores)
        stage_metadata[lifecycle_stage] = {
            "model_scope": "lifecycle_stage_only",
            "stage_row_count": int(len(stage_rows)),
            "training_row_count": int(len(stage_rows)),
            "feature_count": len(selected),
            "feature_list": selected,
            "excluded_features": feature_sets["stages"][lifecycle_stage][
                "excluded_features"
            ],
            "imputation_strategy": "stage-local median",
            "imputation_values": medians,
        }

    if len({id(model.detector) for model in models.values()}) != 3:
        raise RuntimeError("Lifecycle routing did not create three independent detectors")
    combined_scores = pd.concat(scores).sort_index().reset_index(drop=True)
    metadata = {
        "artifact_type": "lifecycle-specific Isolation Forest registry",
        "feature_snapshot_date": feature_snapshot_date,
        "python_version": platform.python_version(),
        "scikit_learn_version": sklearn.__version__,
        "random_state": IFOREST_HYPERPARAMETERS["random_state"],
        "hyperparameters": IFOREST_HYPERPARAMETERS,
        "global_model_used": False,
        "model_count": 3,
        "ground_truth_used_for_training": False,
        "score_semantics": (
            "Higher iforest_unusualness_score and within-stage percentile mean "
            "more statistically unusual within that lifecycle stage; neither is a probability."
        ),
        "stages": stage_metadata,
    }
    return models, combined_scores, metadata


def persist_lifecycle_models(
    models: Mapping[str, LifecycleIsolationModel],
    model_directory: Path,
) -> dict[str, Path]:
    """Persist the three governed stage artifacts under code/models/anomaly."""

    model_directory.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for stage, filename in MODEL_FILENAMES.items():
        path = model_directory / filename
        joblib.dump(models[stage], path)
        paths[stage] = path
    return paths
