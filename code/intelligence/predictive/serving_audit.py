"""Apply Day-6.1 serving governance to frozen artifacts without model fitting."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from intelligence.data.paths import ProjectPaths

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
    apply_shap_serving_contract,
)


FROZEN_DAY6_HASHES = {
    "code/models/predictive/cost_overrun_xgboost.joblib": "C040D5D7F7B22987A8C264848F07B7488403474B0E302C75CB986123D611470F",
    "code/models/predictive/cost_overrun_random_forest.joblib": "E35B9A36103DC32026C6D4FB5C7AFC6ED45F16C49EF908758767475A1A62179B",
    "code/models/predictive/cost_overrun_calibrator.joblib": "664B129C262892C8F0E5EE5B3F7666ACEF5C1641FD46787993A99933C68AEBA8",
    "code/models/predictive/cost_overrun_imputer.joblib": "C64BF7ECE2EAB3470E489AF62EA15988C6C2A37F1D8C8B642A80D85B143864C9",
    "data/processed/evaluation/day6_predictive_metrics.json": "05D7752BEC832A3D671E6AC16DD17C2358E0E2F1118AC3B66D432536499CF4E6",
    "data/processed/evaluation/day6_test_predictions.csv": "E23D0C563D0BE19CE8C9D410600BA0C64F1F87D76C8641FB53EB797F507368D0",
    "data/processed/modeling/day6/predictive_landmark_snapshots.csv": "D1CA5336577836874CC0F0FB927940110FB44E7985E4E1B10B04A0496C99D8AD",
    "data/processed/modeling/day6/delay_training_rows.csv": "9663A1E665B9064EE7305AF9EACA2D618F5E8F7245299ED1DCF7ECA7D86449B8",
    "data/processed/modeling/day6/cost_overrun_training_rows.csv": "6F7167F3771D66A876F9DECEE563C07B00C58DA6AF9C917941D215CBD00B65EB",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def verify_frozen_day6(paths: ProjectPaths) -> None:
    mismatches = {
        relative: (_sha256(paths.project_root / relative), expected)
        for relative, expected in FROZEN_DAY6_HASHES.items()
        if _sha256(paths.project_root / relative) != expected
    }
    if mismatches:
        raise ValueError(f"Frozen Day-6 artifacts changed: {mismatches}")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _distribution(values: pd.Series) -> dict[str, float]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    return {
        "minimum": float(clean.min()),
        "p25": float(clean.quantile(0.25)),
        "median": float(clean.median()),
        "p75": float(clean.quantile(0.75)),
        "maximum": float(clean.max()),
        "mean": float(clean.mean()),
    }


def apply_day6_1_serving_audit(paths: ProjectPaths) -> dict[str, Any]:
    """Migrate serving outputs/metadata only; never instantiate or fit a model."""

    verify_frozen_day6(paths)
    processed = paths.processed_data_dir
    model_metadata_path = paths.models_dir / "predictive" / "predictive_model_metadata.json"
    summary_path = processed / "day6_predictive_summary.json"
    scores_path = processed / "predictive_scores.csv"
    explanations_path = processed / "predictive_explanations.csv"

    model_metadata = json.loads(model_metadata_path.read_text(encoding="utf-8"))
    cost_metadata = model_metadata["targets"]["cost_overrun_outcome"]
    delay_metadata = model_metadata["targets"]["delay_outcome"]
    coefficient = float(cost_metadata["calibration_parameters"]["coefficient"])
    if coefficient >= 0:
        raise ValueError("Day-6.1 rank-reversal policy requires a negative calibration slope")

    original_scores = pd.read_csv(scores_path, low_memory=False)
    original_raw = original_scores["cost_overrun_probability_uncalibrated"].copy()
    original_calibrated = original_scores["cost_overrun_probability_calibrated"].copy()
    scores = apply_cost_overrun_serving_contract(original_scores)
    pd.testing.assert_series_equal(
        scores["cost_overrun_probability_uncalibrated"], original_raw, check_names=False
    )
    pd.testing.assert_series_equal(
        scores["cost_overrun_probability_calibrated"], original_calibrated, check_names=False
    )
    scores.to_csv(scores_path, index=False)

    explanations = pd.read_csv(explanations_path, low_memory=False)
    explanations = apply_shap_serving_contract(explanations, scores)
    explanations.to_csv(explanations_path, index=False)

    cost_metadata.update(
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
            "day6_1_model_retrained": False,
            "day6_1_model_retuned": False,
        }
    )
    delay_metadata.update(
        {
            "model_quality_status": DELAY_MODEL_QUALITY_STATUS,
            "serving_status": DELAY_SERVING_STATUS,
            "serving_score_field": None,
            "day6_1_model_retrained": False,
            "day6_1_model_retuned": False,
        }
    )
    model_metadata["day6_1_serving_safety_audit"] = {
        "calibration_rank_reversal_detected": True,
        "models_retrained": False,
        "models_retuned": False,
        "evaluation_metrics_changed": False,
        "test_set_reused_for_selection": False,
    }
    _write_json(model_metadata_path, model_metadata)

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    execution = scores["lifecycle_stage"].eq("EXECUTION")
    old_distribution = summary["current_probability_distributions"].get("cost_overrun")
    summary["current_probability_distributions"] = {
        "delay": None,
        "cost_overrun_raw_serving": _distribution(
            scores.loc[execution, SERVING_SCORE_FIELD]
        ),
        "cost_overrun_calibrated_diagnostic": old_distribution
        or _distribution(scores.loc[execution, "cost_overrun_probability_calibrated"]),
    }
    summary.update(
        {
            "delay_serving_status": DELAY_SERVING_STATUS,
            "cost_overrun_serving_status": COST_SERVING_STATUS,
            "cost_overrun_calibration_status": CALIBRATION_STATUS,
            "cost_overrun_calibration_serving_eligible": CALIBRATION_SERVING_ELIGIBLE,
            "cost_overrun_model_quality_status": COST_MODEL_QUALITY_STATUS,
            "serving_score_field": SERVING_SCORE_FIELD,
            "serving_score_source_field": SERVING_SCORE_SOURCE_FIELD,
            "serving_percentile_field": SERVING_PERCENTILE_FIELD,
            "serving_rank_field": SERVING_RANK_FIELD,
            "models_retrained_for_day6_1": False,
            "models_retuned_for_day6_1": False,
            "evaluation_metrics_changed_for_day6_1": False,
        }
    )
    _write_json(summary_path, summary)
    verify_frozen_day6(paths)

    future_only = scores.loc[
        execution & ~scores["already_over_sanction_as_of"].astype(bool)
    ].sort_values(
        [SERVING_SCORE_FIELD, "work_id"],
        ascending=[False, True],
        kind="stable",
    )
    top_five = future_only[
        ["work_id", SERVING_SCORE_FIELD, SERVING_PERCENTILE_FIELD, SERVING_RANK_FIELD]
    ].head(5).to_dict(orient="records")
    return {
        "calibration_coefficient": coefficient,
        "calibration_status": CALIBRATION_STATUS,
        "calibration_serving_eligible": CALIBRATION_SERVING_ELIGIBLE,
        "model_quality_status": COST_MODEL_QUALITY_STATUS,
        "serving_score_field": SERVING_SCORE_FIELD,
        "top_five_unobserved_over_sanction": top_five,
        "models_retrained": False,
        "models_retuned": False,
        "evaluation_metrics_changed": False,
    }


def main() -> int:
    result = apply_day6_1_serving_audit(ProjectPaths.discover())
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
