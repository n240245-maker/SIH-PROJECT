"""Small shared fitter for independent Day-6 binary target pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from xgboost import XGBClassifier

from .calibration import SigmoidProbabilityCalibrator, expected_calibration_error
from .splitting import WorkLevelSplit


MINIMUM_CLASS_WORKS = 50
XGBOOST_PARAMETERS: dict[str, Any] = {
    "n_estimators": 300,
    "max_depth": 4,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 5,
    "reg_lambda": 1.0,
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "tree_method": "hist",
    "random_state": 42,
    "n_jobs": -1,
}
RANDOM_FOREST_PARAMETERS: dict[str, Any] = {
    "n_estimators": 500,
    "min_samples_leaf": 5,
    "class_weight": "balanced",
    "random_state": 42,
    "n_jobs": -1,
}


@dataclass(slots=True)
class TrainedTargetModels:
    target: str
    features: tuple[str, ...]
    imputer: SimpleImputer
    xgboost: XGBClassifier
    random_forest: RandomForestClassifier
    calibrator: SigmoidProbabilityCalibrator
    imputer_fit_work_ids: tuple[str, ...]
    split: WorkLevelSplit
    scale_pos_weight: float


def assess_model_feasibility(rows: pd.DataFrame, target: str) -> dict[str, object]:
    unique = rows.groupby("work_id", sort=True)[target].first().dropna().astype("int64")
    positive = int(unique.eq(1).sum())
    negative = int(unique.eq(0).sum())
    feasible = positive >= MINIMUM_CLASS_WORKS and negative >= MINIMUM_CLASS_WORKS
    return {
        "status": "FEASIBLE" if feasible else "INSUFFICIENT_SUPERVISED_OUTCOME_DATA",
        "eligible_work_count": int(len(unique)),
        "positive_work_count": positive,
        "negative_work_count": negative,
        "landmark_row_count": int(len(rows)),
        "positive_prevalence": positive / len(unique) if len(unique) else None,
        "minimum_positive_work_count": MINIMUM_CLASS_WORKS,
        "minimum_negative_work_count": MINIMUM_CLASS_WORKS,
    }


def _matrix(rows: pd.DataFrame, features: tuple[str, ...]) -> pd.DataFrame:
    return rows.loc[:, features].replace([np.inf, -np.inf], np.nan).astype("float64")


def train_target_models(
    rows: pd.DataFrame,
    target: str,
    features: tuple[str, ...],
    split: WorkLevelSplit,
) -> TrainedTargetModels:
    feasibility = assess_model_feasibility(rows, target)
    if feasibility["status"] != "FEASIBLE":
        raise ValueError(f"{target}: {feasibility['status']}")

    train = rows.loc[rows["split"].eq("TRAIN")]
    validation = rows.loc[rows["split"].eq("VALIDATION")]
    x_train = _matrix(train, features)
    x_validation = _matrix(validation, features)
    y_train = train[target].astype("int64").to_numpy()
    y_validation = validation[target].astype("int64").to_numpy()

    imputer = SimpleImputer(strategy="median")
    transformed_train = imputer.fit_transform(x_train)
    transformed_validation = imputer.transform(x_validation)
    train_work_labels = train.groupby("work_id")[target].first().astype("int64")
    positive_train_works = int(train_work_labels.eq(1).sum())
    negative_train_works = int(train_work_labels.eq(0).sum())
    scale_pos_weight = negative_train_works / positive_train_works

    xgb_parameters = dict(XGBOOST_PARAMETERS)
    xgb_parameters["scale_pos_weight"] = scale_pos_weight
    xgb = XGBClassifier(**xgb_parameters)
    xgb.fit(transformed_train, y_train)
    forest = RandomForestClassifier(**RANDOM_FOREST_PARAMETERS)
    forest.fit(transformed_train, y_train)

    validation_probabilities = xgb.predict_proba(transformed_validation)[:, 1]
    calibrator = SigmoidProbabilityCalibrator.fit(
        validation_probabilities,
        y_validation,
        validation["work_id"].to_numpy(),
    )
    return TrainedTargetModels(
        target=target,
        features=features,
        imputer=imputer,
        xgboost=xgb,
        random_forest=forest,
        calibrator=calibrator,
        imputer_fit_work_ids=tuple(sorted(train["work_id"].unique().astype(str))),
        split=split,
        scale_pos_weight=float(scale_pos_weight),
    )


def predict_target_models(
    trained: TrainedTargetModels,
    rows: pd.DataFrame,
) -> pd.DataFrame:
    matrix = trained.imputer.transform(_matrix(rows, trained.features))
    xgb_probability = trained.xgboost.predict_proba(matrix)[:, 1]
    return pd.DataFrame(
        {
            "xgb_probability_uncalibrated": xgb_probability,
            "xgb_probability_calibrated": trained.calibrator.predict(xgb_probability),
            "rf_probability": trained.random_forest.predict_proba(matrix)[:, 1],
        },
        index=rows.index,
    )


def binary_metrics(outcomes: pd.Series, probabilities: pd.Series) -> dict[str, object]:
    y = outcomes.astype("int64").to_numpy()
    p = probabilities.astype("float64").to_numpy()
    if len(np.unique(y)) != 2:
        return {
            "status": "INSUFFICIENT_CLASSES_AT_LANDMARK",
            "row_count": int(len(y)),
            "positive_prevalence": float(y.mean()) if len(y) else None,
            "roc_auc": None,
            "average_precision": None,
            "brier_score": None,
            "expected_calibration_error_10_bins": None,
        }
    return {
        "status": "EVALUATED",
        "row_count": int(len(y)),
        "positive_prevalence": float(y.mean()),
        "roc_auc": float(roc_auc_score(y, p)),
        "average_precision": float(average_precision_score(y, p)),
        "brier_score": float(brier_score_loss(y, p)),
        "expected_calibration_error_10_bins": expected_calibration_error(y, p),
    }
