"""Evaluation-only diagnostic alignment with isolated synthetic ground truth."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from intelligence.data.loader import load_evaluation_ground_truth
from intelligence.data.paths import ProjectPaths


EVALUATION_DISCLAIMERS = (
    "Ground truth was never used for feature selection, preprocessing, model training, tuning, or production ranking.",
    "Metrics measure same-synthetic-snapshot diagnostic alignment only.",
    "Metrics are not production generalization estimates.",
    "Metrics are not validated fraud-detection accuracy.",
    "Evaluation labels represent injected synthetic anomalies.",
)


def _binary_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    positives = int(frame["has_injected_anomaly"].sum())
    negatives = int(len(frame) - positives)
    result: dict[str, Any] = {
        "row_count": int(len(frame)),
        "positive_count": positives,
        "negative_count": negatives,
        "roc_auc": None,
        "average_precision": None,
        "metric_status": "requires both positive and negative classes",
    }
    if positives and negatives:
        labels = frame["has_injected_anomaly"].astype("int8")
        score = frame["within_stage_anomaly_percentile_0_100"]
        result.update(
            {
                "roc_auc": float(roc_auc_score(labels, score)),
                "average_precision": float(average_precision_score(labels, score)),
                "metric_status": "calculated",
            }
        )
    return result


def _top_fraction_metrics(frame: pd.DataFrame, fraction: float) -> dict[str, Any]:
    count = max(1, int(math.ceil(len(frame) * fraction)))
    ranked = frame.sort_values(
        ["within_stage_anomaly_percentile_0_100", "work_id"],
        ascending=[False, True],
        kind="stable",
    )
    selected = ranked.head(count)
    total_positives = int(frame["has_injected_anomaly"].sum())
    selected_positives = int(selected["has_injected_anomaly"].sum())
    return {
        "fraction": fraction,
        "selected_row_count": count,
        "selected_positive_count": selected_positives,
        "precision": float(selected_positives / count),
        "recall": (
            float(selected_positives / total_positives)
            if total_positives
            else None
        ),
    }


def evaluate_production_scores(
    paths: ProjectPaths | None = None,
) -> tuple[Path, Path]:
    """Load labels only after finalized production scoring artifacts exist."""

    resolved = paths or ProjectPaths.discover()
    processed = resolved.processed_data_dir
    score_path = processed / "anomaly_scores.csv"
    metadata_path = resolved.models_dir / "anomaly" / "anomaly_model_metadata.json"
    summary_path = processed / "anomaly_summary.json"
    for required in (score_path, metadata_path, summary_path):
        if not required.is_file():
            raise FileNotFoundError(
                f"Production detector artifacts must be finalized before evaluation: {required}"
            )

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("ground_truth_used_for_training") is not False:
        raise ValueError("Model metadata does not prove the training firewall")
    if int(metadata.get("model_count", 0)) != 3:
        raise ValueError("Expected three finalized lifecycle model artifacts")
    for model_path in metadata.get("model_artifacts", {}).values():
        if not Path(model_path).is_file():
            raise FileNotFoundError(f"Finalized lifecycle model is missing: {model_path}")

    scores = pd.read_csv(score_path, encoding="utf-8", low_memory=False)
    if len(scores) != 3000 or not scores["work_id"].is_unique:
        raise ValueError("Production anomaly scores must contain 3,000 unique works")

    # This is the single intentional evaluation-only access point.
    labels = load_evaluation_ground_truth(resolved)
    evaluation_labels = labels.loc[:, ["work_id", "injected_anomaly_count"]].copy()
    evaluation_labels["has_injected_anomaly"] = evaluation_labels[
        "injected_anomaly_count"
    ].gt(0)
    scored = scores.merge(
        evaluation_labels,
        on="work_id",
        how="left",
        validate="one_to_one",
    )
    if scored["has_injected_anomaly"].isna().any():
        raise ValueError("Evaluation labels do not cover every scored work")

    stage_metrics = {
        str(stage): _binary_metrics(group)
        for stage, group in scored.groupby("lifecycle_stage", sort=True)
    }
    metrics = {
        "artifact_type": "evaluation-only synthetic-label diagnostic",
        "ranking_strategy": (
            "Rank by within-stage anomaly percentile descending; lifecycle-normalized "
            "percentiles are compared overall with work_id as deterministic tie-breaker."
        ),
        "evaluation_label": "has_injected_anomaly = injected_anomaly_count > 0",
        "score_used": "within_stage_anomaly_percentile_0_100",
        "features_or_hyperparameters_changed_after_evaluation": False,
        "disclaimers": list(EVALUATION_DISCLAIMERS),
        "overall": _binary_metrics(scored),
        "by_lifecycle_stage": stage_metrics,
        "ranking_diagnostics": {
            "top_1_percent": _top_fraction_metrics(scored, 0.01),
            "top_5_percent": _top_fraction_metrics(scored, 0.05),
            "top_10_percent": _top_fraction_metrics(scored, 0.10),
        },
    }

    evaluation_directory = processed / "evaluation"
    evaluation_directory.mkdir(parents=True, exist_ok=True)
    scored_path = evaluation_directory / "anomaly_ground_truth_scored.csv"
    metrics_path = evaluation_directory / "anomaly_ground_truth_metrics.json"
    scored.to_csv(scored_path, index=False, encoding="utf-8")
    metrics_path.write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return metrics_path, scored_path


def main() -> int:
    metrics_path, scored_path = evaluate_production_scores()
    print(f"Evaluation-only metrics: {metrics_path}")
    print(f"Evaluation-only scored rows: {scored_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
