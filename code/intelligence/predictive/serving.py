"""Governed serving orientation for frozen Day-6 predictive outputs."""

from __future__ import annotations

import numpy as np
import pandas as pd


CALIBRATION_STATUS = "UNSTABLE_RANK_REVERSAL"
CALIBRATION_SERVING_ELIGIBLE = False
CALIBRATION_SERVING_REASON = (
    "Validation-only sigmoid calibration learned a negative slope and reverses "
    "the primary model ordering. Calibrated probabilities are retained for "
    "diagnostic audit but are not used for operational prioritization."
)
COST_MODEL_QUALITY_STATUS = "PROTOTYPE_WEAK_DISCRIMINATION"
DELAY_MODEL_QUALITY_STATUS = "MODEL_UNAVAILABLE_INSUFFICIENT_CLASS_BALANCE"
COST_SERVING_STATUS = "RAW_XGBOOST_SECONDARY_EARLY_WARNING_EVIDENCE"
DELAY_SERVING_STATUS = "MODEL_UNAVAILABLE_INSUFFICIENT_CLASS_BALANCE"
SERVING_POLICY = (
    "May be displayed as secondary early-warning evidence; must not dominate "
    "final risk fusion."
)
SERVING_SCORE_FIELD = "cost_overrun_serving_score"
SERVING_SCORE_SOURCE_FIELD = "cost_overrun_probability_uncalibrated"
SERVING_PERCENTILE_FIELD = "cost_overrun_serving_percentile_0_100"
SERVING_RANK_FIELD = "cost_overrun_serving_rank"
SHAP_MODEL_OUTPUT = "xgboost_raw_margin"


def percentile_0_100(values: pd.Series) -> pd.Series:
    result = pd.Series(np.nan, index=values.index, dtype="float64")
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return result
    if len(clean) == 1:
        result.loc[clean.index] = 100.0
    else:
        ranks = clean.rank(method="average", ascending=True)
        result.loc[clean.index] = (ranks - 1.0) / (len(clean) - 1.0) * 100.0
    return result


def serving_rank(scores: pd.DataFrame, applicable: pd.Series) -> pd.Series:
    """Rank high raw probability first, with work ID as deterministic tie-breaker."""

    result = pd.Series(pd.NA, index=scores.index, dtype="Int64")
    candidates = scores.loc[
        applicable & scores[SERVING_SCORE_SOURCE_FIELD].notna(),
        ["work_id", SERVING_SCORE_SOURCE_FIELD],
    ].copy()
    candidates = candidates.sort_values(
        [SERVING_SCORE_SOURCE_FIELD, "work_id"],
        ascending=[False, True],
        kind="stable",
    )
    result.loc[candidates.index] = np.arange(1, len(candidates) + 1, dtype="int64")
    return result


def apply_cost_overrun_serving_contract(scores: pd.DataFrame) -> pd.DataFrame:
    """Add the Day-6.1 raw-XGBoost serving fields without changing probabilities."""

    required = {
        "work_id",
        "lifecycle_stage",
        "cost_overrun_probability_uncalibrated",
        "cost_overrun_probability_calibrated",
        "already_over_sanction_as_of",
    }
    missing = required.difference(scores.columns)
    if missing:
        raise ValueError(f"Predictive scores lack serving inputs: {sorted(missing)}")
    if len(scores) != 3_000 or not scores["work_id"].is_unique:
        raise ValueError("Predictive serving contract requires 3,000 unique work IDs")

    result = scores.copy()
    execution = result["lifecycle_stage"].eq("EXECUTION")
    raw = pd.to_numeric(result[SERVING_SCORE_SOURCE_FIELD], errors="coerce")
    if raw.loc[execution].isna().any() or not raw.loc[execution].between(0, 1).all():
        raise ValueError("Every execution work must retain a bounded raw XGBoost score")

    result["cost_overrun_model_score_raw_probability"] = raw
    result["cost_overrun_calibration_status"] = CALIBRATION_STATUS
    result["cost_overrun_calibration_serving_eligible"] = CALIBRATION_SERVING_ELIGIBLE
    result["cost_overrun_model_quality_status"] = COST_MODEL_QUALITY_STATUS
    result[SERVING_SCORE_FIELD] = raw.where(execution)
    serving_percentile = percentile_0_100(result.loc[execution, SERVING_SCORE_FIELD])
    result[SERVING_PERCENTILE_FIELD] = serving_percentile.reindex(result.index)
    result[SERVING_RANK_FIELD] = serving_rank(result, execution)

    # Backward-compatible percentile names now follow the governed serving score.
    result["cost_overrun_prediction_percentile_0_100"] = result[
        SERVING_PERCENTILE_FIELD
    ]
    result["cost_overrun_percentile_within_applicable_execution"] = result[
        SERVING_PERCENTILE_FIELD
    ]
    return result


def apply_shap_serving_contract(
    explanations: pd.DataFrame,
    scores: pd.DataFrame,
) -> pd.DataFrame:
    """Make explicit that SHAP and serving ranking refer to the raw XGBoost model."""

    score_lookup = scores[["work_id", SERVING_SCORE_FIELD]].rename(
        columns={SERVING_SCORE_FIELD: "raw_model_probability"}
    )
    result = explanations.drop(
        columns=[
            "raw_model_probability",
            "model_output_explained",
            "serving_score_field",
            "calibrated_probability_role",
        ],
        errors="ignore",
    ).merge(score_lookup, on="work_id", how="left", validate="one_to_one")
    if result["raw_model_probability"].isna().any():
        raise ValueError("Every SHAP explanation must align to a raw serving score")
    result["model_output_explained"] = SHAP_MODEL_OUTPUT
    result["serving_score_field"] = SERVING_SCORE_FIELD
    result["calibrated_probability_role"] = "DIAGNOSTIC_AUDIT_ONLY_NOT_EXPLAINED_BY_SHAP"
    preferred = [
        "work_id",
        "prediction_target",
        "raw_model_probability",
        "calibrated_probability",
        "model_output_explained",
        "serving_score_field",
        "calibrated_probability_role",
        "base_probability",
        "explanation_scope",
    ]
    return result[preferred + [column for column in result if column not in preferred]]
