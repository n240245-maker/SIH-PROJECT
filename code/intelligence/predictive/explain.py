"""Non-causal SHAP evidence for current XGBoost predictions."""

from __future__ import annotations

import numpy as np
import pandas as pd
import shap
from scipy.special import expit

from .modeling import TrainedTargetModels
from .serving import SERVING_SCORE_FIELD, SHAP_MODEL_OUTPUT


EXPLANATION_SCOPE = (
    "SHAP contribution to the XGBoost model output; non-causal and not proof of "
    "why an outcome will occur."
)


def build_shap_explanations(
    trained: TrainedTargetModels,
    rows: pd.DataFrame,
    raw_model_probabilities: np.ndarray,
    calibrated_probabilities: np.ndarray,
    *,
    prediction_target: str,
) -> pd.DataFrame:
    """Retain the three strongest absolute SHAP contributors per scored work."""

    raw = rows.loc[:, trained.features].replace([np.inf, -np.inf], np.nan).astype("float64")
    matrix = trained.imputer.transform(raw)
    explainer = shap.TreeExplainer(trained.xgboost)
    shap_values = np.asarray(explainer.shap_values(matrix), dtype="float64")
    if shap_values.ndim == 3:
        shap_values = shap_values[:, :, -1]
    expected = np.asarray(explainer.expected_value, dtype="float64").reshape(-1)
    base_margin = float(expected[-1])
    base_probability = float(expit(base_margin))

    records: list[dict[str, object]] = []
    for position, (_, row) in enumerate(rows.iterrows()):
        order = np.argsort(np.abs(shap_values[position]))[::-1][:3]
        record: dict[str, object] = {
            "work_id": str(row["work_id"]),
            "prediction_target": prediction_target,
            "raw_model_probability": float(raw_model_probabilities[position]),
            "model_output_explained": SHAP_MODEL_OUTPUT,
            "serving_score_field": SERVING_SCORE_FIELD,
            "calibrated_probability_role": (
                "DIAGNOSTIC_AUDIT_ONLY_NOT_EXPLAINED_BY_SHAP"
            ),
            "base_probability": base_probability,
            "calibrated_probability": float(calibrated_probabilities[position]),
            "explanation_scope": EXPLANATION_SCOPE,
        }
        for rank, feature_index in enumerate(order, start=1):
            feature = trained.features[int(feature_index)]
            original_value = raw.iloc[position][feature]
            record[f"top_feature_{rank}"] = feature
            record[f"top_feature_{rank}_value"] = (
                None if pd.isna(original_value) else float(original_value)
            )
            record[f"top_feature_{rank}_shap"] = float(
                shap_values[position, int(feature_index)]
            )
        records.append(record)
    return pd.DataFrame.from_records(records)
