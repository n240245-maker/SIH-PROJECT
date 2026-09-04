"""Day-7 operational trends and explainable review-priority production runner."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from intelligence.data.config import load_settings
from intelligence.data.loader import load_operational_data
from intelligence.data.paths import ProjectPaths
from intelligence.trends.context import build_work_trend_context
from intelligence.trends.hotspots import build_detector_hotspots
from intelligence.trends.monthly import (
    TREND_METRICS,
    build_trend_alerts,
    build_trend_timeseries,
    latest_complete_month,
)

from .alerts import build_review_alerts
from .fusion import (
    build_authority_summary,
    build_contribution_evidence,
    build_review_priority_queue,
    build_review_priority_scores,
)
from .policy import LIFECYCLE_WEIGHTS, POLICY_VERSION, policy_document
from .signals import build_family_signals


FROZEN_INPUTS = (
    "data/processed/project_features.csv",
    "data/processed/anomaly_scores.csv",
    "data/processed/peer_benchmark_summary.csv",
    "data/processed/peer_benchmark_evidence.csv",
    "data/processed/duplicate_summary.csv",
    "data/processed/duplicate_candidates.csv",
    "data/processed/payment_irregularity_summary.csv",
    "data/processed/payment_irregularities.csv",
    "data/processed/fund_progress_evidence.csv",
    "data/processed/compliance_summary.csv",
    "data/processed/compliance_evidence.csv",
    "data/processed/predictive_scores.csv",
    "data/processed/predictive_explanations.csv",
    "data/processed/day6_predictive_summary.json",
    "code/models/predictive/predictive_model_metadata.json",
    "code/models/predictive/cost_overrun_xgboost.joblib",
    "code/models/predictive/cost_overrun_random_forest.joblib",
    "code/models/predictive/cost_overrun_calibrator.joblib",
    "code/models/predictive/cost_overrun_imputer.joblib",
    "data/processed/evaluation/day6_predictive_metrics.json",
    "data/processed/evaluation/day6_test_predictions.csv",
    "data/processed/modeling/day6/predictive_landmark_snapshots.csv",
    "data/processed/modeling/day6/delay_training_rows.csv",
    "data/processed/modeling/day6/cost_overrun_training_rows.csv",
)

OUTPUT_PATHS = {
    "trend_timeseries": "data/processed/trend_timeseries.csv",
    "trend_alerts": "data/processed/trend_alerts.csv",
    "detector_hotspots": "data/processed/detector_hotspots.csv",
    "work_trend_context": "data/processed/work_trend_context.csv",
    "risk_fusion_policy": "data/processed/risk_fusion_policy.json",
    "review_priority_evidence": "data/processed/review_priority_evidence.csv",
    "review_priority_scores": "data/processed/review_priority_scores.csv",
    "review_priority_queue": "data/processed/review_priority_queue.csv",
    "review_alerts": "data/processed/review_alerts.csv",
    "review_priority_authority_summary": "data/processed/review_priority_authority_summary.csv",
    "day7_intelligence_summary": "data/processed/day7_intelligence_summary.json",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def frozen_hashes(paths: ProjectPaths) -> dict[str, str]:
    missing = [relative for relative in FROZEN_INPUTS if not (paths.project_root / relative).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing frozen Day-7 input artifacts: {missing}")
    return {relative: _sha256(paths.project_root / relative) for relative in FROZEN_INPUTS}


def _read_csv(processed: Path, filename: str) -> pd.DataFrame:
    return pd.read_csv(processed / filename, low_memory=False)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    def default(value: object):
        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.floating,)):
            return None if np.isnan(value) else float(value)
        if isinstance(value, (np.bool_,)):
            return bool(value)
        if isinstance(value, pd.Timestamp):
            return value.isoformat()
        raise TypeError(f"Cannot JSON-serialize {type(value)!r}")

    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=default) + "\n",
        encoding="utf-8",
    )


def _validate_predictive_governance(paths: ProjectPaths) -> None:
    summary = json.loads(
        (paths.processed_data_dir / "day6_predictive_summary.json").read_text(encoding="utf-8")
    )
    metadata = json.loads(
        (paths.models_dir / "predictive" / "predictive_model_metadata.json").read_text(encoding="utf-8")
    )
    cost = metadata["targets"]["cost_overrun_outcome"]
    delay = metadata["targets"]["delay_outcome"]
    requirements = {
        "calibration_status": "UNSTABLE_RANK_REVERSAL",
        "calibration_serving_eligible": False,
        "model_quality_status": "PROTOTYPE_WEAK_DISCRIMINATION",
        "serving_percentile_field": "cost_overrun_serving_percentile_0_100",
    }
    for field, expected in requirements.items():
        if cost.get(field) != expected or summary.get(
            "cost_overrun_" + field if field != "serving_percentile_field" else "serving_percentile_field"
        ) != expected:
            raise ValueError(f"Predictive serving metadata mismatch for {field}")
    if delay.get("serving_score_field") is not None:
        raise ValueError("Unavailable delay model unexpectedly exposes a serving score")


def _distribution(values: pd.Series) -> dict[str, float]:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    return {
        "minimum": float(numeric.min()),
        "p25": float(numeric.quantile(0.25)),
        "median": float(numeric.median()),
        "mean": float(numeric.mean()),
        "p75": float(numeric.quantile(0.75)),
        "p90": float(numeric.quantile(0.90)),
        "maximum": float(numeric.max()),
    }


def _band_counts(scores: pd.DataFrame) -> dict[str, int]:
    counts = scores["review_priority_band"].value_counts()
    return {band: int(counts.get(band, 0)) for band in ("LOW", "MEDIUM", "HIGH", "CRITICAL")}


def _lifecycle_summary(scores: pd.DataFrame) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for lifecycle in ("PRE_SANCTION", "EXECUTION", "COMPLETION"):
        group = scores.loc[scores["lifecycle_stage"].eq(lifecycle)]
        values = group["review_priority_score_0_100"]
        result[lifecycle] = {
            "population": int(len(group)),
            "mean_priority_score": float(values.mean()),
            "median_priority_score": float(values.median()),
            "p90_priority_score": float(values.quantile(0.90)),
            "maximum_priority_score": float(values.max()),
            "band_counts": _band_counts(group),
        }
    return result


def _summary_payload(
    latest_month: str,
    timeseries: pd.DataFrame,
    trend_alerts: pd.DataFrame,
    hotspots: pd.DataFrame,
    scores: pd.DataFrame,
    evidence: pd.DataFrame,
    queue: pd.DataFrame,
    review_alerts: pd.DataFrame,
    frozen_before: dict[str, str],
) -> dict[str, object]:
    ranked = scores.sort_values(
        ["review_priority_score_0_100", "work_id"], ascending=[False, True], kind="stable"
    )
    top_fields = [
        "work_id",
        "lifecycle_stage",
        "review_priority_score_0_100",
        "review_priority_band",
        "fusion_evidence_coverage_pct",
        "top_contributor_1_family",
        "top_contributor_1_points",
        "top_contributor_2_family",
        "top_contributor_2_points",
        "top_contributor_3_family",
        "top_contributor_3_points",
    ]
    top_ten = ranked[top_fields].head(10).to_dict(orient="records")
    top_five_ids = set(ranked.head(5)["work_id"])
    top_five_contributions = evidence.loc[evidence["work_id"].isin(top_five_ids)].sort_values(
        ["work_id", "contribution_points", "family"],
        ascending=[True, False, True],
        kind="stable",
    ).to_dict(orient="records")
    trend_examples = trend_alerts.assign(_abs_z=trend_alerts["robust_z"].abs()).sort_values(
        ["_abs_z", "month", "group_type", "group_value", "metric"],
        ascending=[False, False, True, True, True],
        kind="stable",
    ).drop(columns="_abs_z").head(10).to_dict(orient="records")
    hotspot_counts = hotspots["group_type"].value_counts().sort_index()
    alert_counts = review_alerts["alert_type"].value_counts().sort_index()
    return {
        "as_of_date": "2026-09-01",
        "latest_complete_trend_month": latest_month,
        "trend_metrics": list(TREND_METRICS),
        "trend_metric_count": len(TREND_METRICS),
        "trend_timeseries_row_count": int(len(timeseries)),
        "trend_alert_count": int(len(trend_alerts)),
        "strongest_trend_examples": trend_examples,
        "hotspot_group_counts": {
            "total": int(len(hotspots)),
            "by_group_type": {key: int(value) for key, value in hotspot_counts.items()},
        },
        "risk_fusion_policy_version": POLICY_VERSION,
        "lifecycle_weight_maps_pct": LIFECYCLE_WEIGHTS,
        "priority_band_counts_overall": _band_counts(scores),
        "priority_summary_by_lifecycle": _lifecycle_summary(scores),
        "high_critical_queue_count": int(len(queue)),
        "top_review_priority_cases": top_ten,
        "top_five_family_contributions": top_five_contributions,
        "fusion_evidence_coverage_distribution": _distribution(
            scores["fusion_evidence_coverage_pct"]
        ),
        "fusion_evidence_coverage_by_lifecycle": {
            lifecycle: _distribution(group["fusion_evidence_coverage_pct"])
            for lifecycle, group in scores.groupby("lifecycle_stage", sort=True)
        },
        "review_alert_counts": {key: int(value) for key, value in alert_counts.items()},
        "double_counting_controls": {
            "released_total_exceeds_sanction": "assigned only to OBSERVED_CONDITIONS; excluded from PAYMENT_EXECUTION",
            "fund_progress_vs_expenditure": "combined by maximum inside one capped PAYMENT_EXECUTION family",
            "anomaly_vs_peer": "separate families; repeated peer evidence reduced to one lifecycle-local family score",
            "completion_timing_vs_overdue": "observed overdue applies only to EXECUTION; completion compliance remains separate",
            "detector_hotspots": "dashboard aggregate only; never consumed by work-level trend or fusion functions",
        },
        "predictive_governance": {
            "calibrated_cost_probability_fused": False,
            "cost_signal_role": "weak secondary raw-XGBoost serving percentile; maximum 5 execution points",
            "delay_model_signal_contribution": 0,
        },
        "artifact_paths": OUTPUT_PATHS,
        "frozen_input_hashes_verified_before_and_after": frozen_before,
        "governance_statement": (
            "Review priority is deterministic human-review prioritization, not a "
            "probability, finding, verdict, or automatic decision."
        ),
        "ground_truth_used": False,
        "detector_hotspot_feedback_used": False,
    }


def run_day7(paths: ProjectPaths, as_of_date=None) -> dict[str, object]:
    settings = load_settings(paths, as_of_date=as_of_date)
    if settings.as_of_date.isoformat() != "2026-09-01":
        raise ValueError("Day-7 controlled snapshot must be AS_OF_DATE=2026-09-01")
    frozen_before = frozen_hashes(paths)
    _validate_predictive_governance(paths)
    processed = paths.ensure_processed_data_dir()
    bundle = load_operational_data(paths)

    features = _read_csv(processed, "project_features.csv")
    anomaly = _read_csv(processed, "anomaly_scores.csv")
    peer = _read_csv(processed, "peer_benchmark_summary.csv")
    duplicates = _read_csv(processed, "duplicate_summary.csv")
    payment_summary = _read_csv(processed, "payment_irregularity_summary.csv")
    payment_evidence = _read_csv(processed, "payment_irregularities.csv")
    fund_progress = _read_csv(processed, "fund_progress_evidence.csv")
    compliance_summary = _read_csv(processed, "compliance_summary.csv")
    compliance_evidence = _read_csv(processed, "compliance_evidence.csv")
    predictive = _read_csv(processed, "predictive_scores.csv")

    latest_month = str(latest_complete_month(settings.as_of_date))
    timeseries = build_trend_timeseries(bundle, settings.as_of_date)
    trend_alerts = build_trend_alerts(timeseries)
    trend_context = build_work_trend_context(features, timeseries, latest_month)
    hotspots = build_detector_hotspots(
        features,
        anomaly,
        duplicates,
        payment_summary,
        fund_progress,
        compliance_summary,
        predictive,
        bundle.entities,
    )
    signals = build_family_signals(
        features,
        anomaly,
        peer,
        duplicates,
        payment_summary,
        payment_evidence,
        fund_progress,
        compliance_evidence,
        predictive,
        trend_context,
    )
    evidence = build_contribution_evidence(features, signals)
    scores = build_review_priority_scores(
        features, evidence, duplicates, payment_summary, compliance_summary, predictive
    )
    queue = build_review_priority_queue(scores)
    review_alerts = build_review_alerts(
        features,
        anomaly,
        peer,
        duplicates,
        payment_evidence,
        fund_progress,
        compliance_evidence,
        predictive,
        trend_context,
        signals,
    )
    authority = build_authority_summary(features, scores)

    timeseries.to_csv(processed / "trend_timeseries.csv", index=False)
    trend_alerts.to_csv(processed / "trend_alerts.csv", index=False)
    hotspots.to_csv(processed / "detector_hotspots.csv", index=False)
    trend_context.to_csv(processed / "work_trend_context.csv", index=False)
    evidence.to_csv(processed / "review_priority_evidence.csv", index=False)
    scores.to_csv(processed / "review_priority_scores.csv", index=False)
    queue.to_csv(processed / "review_priority_queue.csv", index=False)
    review_alerts.to_csv(processed / "review_alerts.csv", index=False)
    authority.to_csv(processed / "review_priority_authority_summary.csv", index=False)
    _write_json(processed / "risk_fusion_policy.json", policy_document())

    frozen_after = frozen_hashes(paths)
    if frozen_before != frozen_after:
        changed = {
            path: (frozen_before[path], frozen_after[path])
            for path in frozen_before
            if frozen_before[path] != frozen_after[path]
        }
        raise RuntimeError(f"Day-7 changed frozen inputs: {changed}")
    summary = _summary_payload(
        latest_month,
        timeseries,
        trend_alerts,
        hotspots,
        scores,
        evidence,
        queue,
        review_alerts,
        frozen_before,
    )
    _write_json(processed / "day7_intelligence_summary.json", summary)
    return summary


def main() -> int:
    summary = run_day7(ProjectPaths.discover())
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
