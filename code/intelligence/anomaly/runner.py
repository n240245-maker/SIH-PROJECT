"""Production Day-3 runner; intentionally independent of evaluation labels."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from intelligence.data.config import load_settings
from intelligence.data.paths import ProjectPaths

from .feature_selection import select_lifecycle_feature_sets
from .isolation import (
    IFOREST_HYPERPARAMETERS,
    persist_lifecycle_models,
    train_lifecycle_models,
)
from .peer_benchmark import build_peer_benchmarks
from .scoring import attach_peer_context, build_anomaly_evidence


@dataclass(frozen=True, slots=True)
class ProductionArtifacts:
    anomaly_feature_sets: Path
    peer_benchmark_evidence: Path
    peer_benchmark_summary: Path
    anomaly_scores: Path
    anomaly_evidence: Path
    anomaly_summary: Path
    model_metadata: Path
    model_artifacts: dict[str, Path]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Required governed Day-2 artifact is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _score_distribution(scores: pd.DataFrame) -> dict[str, dict[str, float | int]]:
    distributions: dict[str, dict[str, float | int]] = {}
    for stage, group in scores.groupby("lifecycle_stage", sort=True):
        values = group["iforest_unusualness_score"]
        distributions[str(stage)] = {
            "row_count": int(len(group)),
            "minimum": float(values.min()),
            "maximum": float(values.max()),
            "mean": float(values.mean()),
            "standard_deviation": float(values.std(ddof=1)),
        }
    return distributions


def run_production_detector(
    paths: ProjectPaths | None = None,
    *,
    as_of_date: date | str | None = None,
) -> ProductionArtifacts:
    """Generate all production detector artifacts without evaluation data."""

    resolved = paths or ProjectPaths.discover()
    settings = load_settings(resolved, as_of_date=as_of_date)
    processed = resolved.ensure_processed_data_dir().resolve()
    expected_processed = (resolved.project_root / "data" / "processed").resolve()
    if processed != expected_processed:
        raise ValueError(f"Day-3 outputs must use {expected_processed}, not {processed}")

    feature_path = processed / "project_features.csv"
    catalog_path = processed / "feature_catalog.json"
    quality_path = processed / "feature_quality_profile.json"
    if not feature_path.is_file():
        raise FileNotFoundError(f"Build Day-2 features first: {feature_path}")
    feature_hash_before = _sha256(feature_path)
    features = pd.read_csv(feature_path, encoding="utf-8", low_memory=False)
    catalog = _read_json(catalog_path)
    quality = _read_json(quality_path)

    snapshot_date = str(catalog.get("feature_snapshot_date"))
    if snapshot_date != settings.as_of_date.isoformat():
        raise ValueError(
            f"Catalog snapshot {snapshot_date} does not match AS_OF_DATE "
            f"{settings.as_of_date.isoformat()}"
        )
    if len(features) != 3000 or not features["work_id"].is_unique:
        raise ValueError("Day-3 input must contain 3,000 unique work rows")
    if int(quality.get("row_count", -1)) != len(features):
        raise ValueError("Feature quality profile does not match the feature snapshot")
    if int(catalog.get("generic_anomaly_eligible_feature_count", -1)) != 32:
        raise ValueError("Expected the governed Day-2.1 pool of 32 candidates")

    feature_sets = select_lifecycle_feature_sets(features, catalog)
    feature_sets["feature_snapshot_date"] = snapshot_date
    feature_sets["source_feature_artifact"] = str(feature_path)
    feature_sets["source_feature_sha256"] = feature_hash_before
    feature_sets_path = _write_json(
        processed / "anomaly_feature_sets.json", feature_sets
    )

    peer_evidence, peer_summary, peer_metrics = build_peer_benchmarks(
        features, feature_sets
    )
    peer_evidence_path = processed / "peer_benchmark_evidence.csv"
    peer_summary_path = processed / "peer_benchmark_summary.csv"
    peer_evidence.to_csv(peer_evidence_path, index=False, encoding="utf-8")
    peer_summary.to_csv(peer_summary_path, index=False, encoding="utf-8")

    models, isolation_scores, metadata = train_lifecycle_models(
        features,
        feature_sets,
        feature_snapshot_date=snapshot_date,
    )
    model_directory = (resolved.models_dir / "anomaly").resolve()
    expected_model_directory = (
        resolved.project_root / "code" / "models" / "anomaly"
    ).resolve()
    if model_directory != expected_model_directory:
        raise ValueError(
            f"Day-3 models must use {expected_model_directory}, not {model_directory}"
        )
    model_paths = persist_lifecycle_models(models, model_directory)
    metadata["model_artifacts"] = {
        stage: str(path) for stage, path in model_paths.items()
    }
    metadata_path = _write_json(
        model_directory / "anomaly_model_metadata.json", metadata
    )

    anomaly_scores = attach_peer_context(isolation_scores, peer_summary)
    anomaly_scores_path = processed / "anomaly_scores.csv"
    anomaly_scores.to_csv(anomaly_scores_path, index=False, encoding="utf-8")
    anomaly_evidence = build_anomaly_evidence(anomaly_scores, peer_evidence)
    anomaly_evidence_path = processed / "anomaly_evidence.csv"
    anomaly_evidence.to_csv(anomaly_evidence_path, index=False, encoding="utf-8")

    distinct_metrics = sorted(
        {metric for metrics in peer_metrics.values() for metric in metrics}
    )
    summary = {
        "artifact_type": "production anomaly detector summary",
        "feature_snapshot_date": snapshot_date,
        "interpretation": (
            "Anomaly means statistically unusual relative to comparable records; "
            "scores are not probabilities or automated verdicts."
        ),
        "stage_counts": {
            stage: int(count)
            for stage, count in features["lifecycle_stage"].value_counts().items()
        },
        "stage_feature_counts": {
            stage: int(details["selected_feature_count"])
            for stage, details in feature_sets["stages"].items()
        },
        "model_hyperparameters": IFOREST_HYPERPARAMETERS,
        "score_distribution_by_stage": _score_distribution(anomaly_scores),
        "peer_benchmark": {
            "minimum_peer_group_size": 20,
            "stage_metrics": peer_metrics,
            "distinct_metric_count": len(distinct_metrics),
            "distinct_metrics": distinct_metrics,
            "evidence_row_count": int(len(peer_evidence)),
            "statistical_peer_outlier_evidence_row_count": int(
                peer_evidence["statistical_peer_outlier"].sum()
            ),
        },
        "artifact_paths": {
            "anomaly_feature_sets": str(feature_sets_path),
            "peer_benchmark_evidence": str(peer_evidence_path),
            "peer_benchmark_summary": str(peer_summary_path),
            "anomaly_scores": str(anomaly_scores_path),
            "anomaly_evidence": str(anomaly_evidence_path),
            "model_metadata": str(metadata_path),
            "models": {stage: str(path) for stage, path in model_paths.items()},
        },
        "source_feature_sha256": feature_hash_before,
    }
    anomaly_summary_path = _write_json(
        processed / "anomaly_summary.json", summary
    )
    if _sha256(feature_path) != feature_hash_before:
        raise RuntimeError("project_features.csv changed during Day-3 generation")

    return ProductionArtifacts(
        anomaly_feature_sets=feature_sets_path,
        peer_benchmark_evidence=peer_evidence_path,
        peer_benchmark_summary=peer_summary_path,
        anomaly_scores=anomaly_scores_path,
        anomaly_evidence=anomaly_evidence_path,
        anomaly_summary=anomaly_summary_path,
        model_metadata=metadata_path,
        model_artifacts=model_paths,
    )


def main() -> int:
    artifacts = run_production_detector()
    print(f"Anomaly feature sets: {artifacts.anomaly_feature_sets}")
    print(f"Peer evidence: {artifacts.peer_benchmark_evidence}")
    print(f"Peer summary: {artifacts.peer_benchmark_summary}")
    print(f"Anomaly scores: {artifacts.anomaly_scores}")
    print(f"Anomaly evidence: {artifacts.anomaly_evidence}")
    print(f"Detector summary: {artifacts.anomaly_summary}")
    print(f"Model metadata: {artifacts.model_metadata}")
    for stage, path in artifacts.model_artifacts.items():
        print(f"{stage} model: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
