"""Unified Day-4 production runner for independent detector artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import pandas as pd

from intelligence.data.config import load_settings
from intelligence.data.loader import load_operational_data
from intelligence.data.paths import ProjectPaths
from intelligence.duplicates.runner import duplicate_audit_payload, run_duplicate_detector
from intelligence.payments.irregularities import (
    SIGNAL_POLICY,
    build_payment_irregularities,
)

from .fund_progress import (
    LARGE_POSITIVE_GAP_HEURISTIC_PCT,
    PERSISTENT_REPORT_COUNT_HEURISTIC,
    build_fund_progress_evidence,
)


@dataclass(frozen=True, slots=True)
class Day4Artifacts:
    duplicate_candidates: Path
    duplicate_summary: Path
    payment_irregularities: Path
    payment_summary: Path
    fund_progress_evidence: Path
    detector_summary: Path


def _distribution(values: pd.Series) -> dict[str, float | int | None]:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if numeric.empty:
        return {
            "count": 0,
            "minimum": None,
            "q1": None,
            "median": None,
            "mean": None,
            "q3": None,
            "p90": None,
            "maximum": None,
        }
    return {
        "count": int(len(numeric)),
        "minimum": float(numeric.min()),
        "q1": float(numeric.quantile(0.25)),
        "median": float(numeric.median()),
        "mean": float(numeric.mean()),
        "q3": float(numeric.quantile(0.75)),
        "p90": float(numeric.quantile(0.90)),
        "maximum": float(numeric.max()),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def run_day4_detectors(paths: ProjectPaths | None = None) -> Day4Artifacts:
    """Generate separate duplicate, payment, and execution evidence outputs."""

    resolved = paths or ProjectPaths.discover()
    settings = load_settings(resolved)
    processed = resolved.ensure_processed_data_dir().resolve()
    expected = (resolved.project_root / "data" / "processed").resolve()
    if processed != expected:
        raise ValueError(f"Day-4 outputs must use {expected}, not {processed}")

    feature_path = processed / "project_features.csv"
    if not feature_path.is_file():
        raise FileNotFoundError(f"Governed Day-2 features are missing: {feature_path}")
    features = pd.read_csv(feature_path, encoding="utf-8", low_memory=False)
    if len(features) != 3000 or not features["work_id"].is_unique:
        raise ValueError("Day-4 project features must contain 3,000 unique works")

    duplicate_artifacts = run_duplicate_detector(resolved)
    duplicate_candidates = pd.read_csv(duplicate_artifacts.candidates)
    duplicate_summary = pd.read_csv(duplicate_artifacts.summary)

    bundle = load_operational_data(resolved)
    payment_irregularities, payment_summary = build_payment_irregularities(
        bundle.payments, features, settings.as_of_date
    )
    payment_path = processed / "payment_irregularities.csv"
    payment_summary_path = processed / "payment_irregularity_summary.csv"
    payment_irregularities.to_csv(payment_path, index=False, encoding="utf-8")
    payment_summary.to_csv(payment_summary_path, index=False, encoding="utf-8")

    fund_progress = build_fund_progress_evidence(
        features, bundle.progress, settings.as_of_date
    )
    fund_progress_path = processed / "fund_progress_evidence.csv"
    fund_progress.to_csv(fund_progress_path, index=False, encoding="utf-8")

    payment_counts = {
        code: int(payment_irregularities["signal_code"].eq(code).sum())
        for code in SIGNAL_POLICY
    }
    embedding_metadata_path = processed / "duplicate_work_embeddings_metadata.json"
    embedding_metadata = json.loads(
        embedding_metadata_path.read_text(encoding="utf-8")
    )
    summary = {
        "artifact_type": "Day-4 independent detector summary",
        "feature_snapshot_date": settings.as_of_date.isoformat(),
        "governance": (
            "Duplicate similarity, payment evidence, and fund-progress evidence "
            "remain independent review signals; no fused score or final decision exists."
        ),
        "duplicates": duplicate_audit_payload(
            duplicate_candidates, duplicate_summary, embedding_metadata
        ),
        "payments": {
            "signal_counts_by_code": payment_counts,
            "total_evidence_rows": int(len(payment_irregularities)),
            "works_with_evidence": int(
                payment_summary["has_payment_irregularity_evidence"].sum()
            ),
        },
        "fund_progress": {
            "applicable_work_count": int(len(fund_progress)),
            "large_positive_gap_engineering_heuristic_pct": LARGE_POSITIVE_GAP_HEURISTIC_PCT,
            "persistent_report_count_engineering_heuristic": PERSISTENT_REPORT_COUNT_HEURISTIC,
            "fund_minus_physical_gap_distribution": _distribution(
                fund_progress["fund_minus_physical_gap_pct_as_of"]
            ),
            "reported_vs_payment_difference_distribution": _distribution(
                fund_progress[
                    "reported_vs_payment_financial_progress_difference_pct"
                ]
            ),
            "works_with_persistent_large_reported_gap_evidence": int(
                fund_progress[
                    "persistent_large_reported_gap_review_heuristic"
                ].sum()
            ),
            "works_with_current_large_positive_fund_gap_evidence": int(
                fund_progress[
                    "current_large_positive_fund_gap_review_heuristic"
                ].sum()
            ),
            "status_not_started_with_payment_evidence": int(
                fund_progress["status_not_started_with_payment_evidence"].sum()
            ),
            "status_not_started_with_physical_progress": int(
                fund_progress[
                    "status_not_started_with_physical_progress"
                ].sum()
            ),
        },
        "artifact_paths": {
            "duplicate_work_embeddings": str(duplicate_artifacts.embeddings),
            "duplicate_embedding_metadata": str(duplicate_artifacts.embedding_metadata),
            "duplicate_candidates": str(duplicate_artifacts.candidates),
            "duplicate_summary": str(duplicate_artifacts.summary),
            "payment_irregularities": str(payment_path),
            "payment_irregularity_summary": str(payment_summary_path),
            "fund_progress_evidence": str(fund_progress_path),
        },
    }
    detector_summary_path = _write_json(
        processed / "day4_detector_summary.json", summary
    )
    return Day4Artifacts(
        duplicate_candidates=duplicate_artifacts.candidates,
        duplicate_summary=duplicate_artifacts.summary,
        payment_irregularities=payment_path,
        payment_summary=payment_summary_path,
        fund_progress_evidence=fund_progress_path,
        detector_summary=detector_summary_path,
    )


def main() -> int:
    artifacts = run_day4_detectors()
    print(f"Duplicate candidates: {artifacts.duplicate_candidates}")
    print(f"Duplicate summary: {artifacts.duplicate_summary}")
    print(f"Payment irregularities: {artifacts.payment_irregularities}")
    print(f"Payment summary: {artifacts.payment_summary}")
    print(f"Fund-progress evidence: {artifacts.fund_progress_evidence}")
    print(f"Day-4 detector summary: {artifacts.detector_summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
