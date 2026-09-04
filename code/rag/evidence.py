"""Deterministic, minimized evidence bundles built only from frozen artifacts."""

from __future__ import annotations

import json
import math
import re
from typing import Any

import numpy as np
import pandas as pd

from intelligence.data.paths import ProjectPaths


SINGLE_TABLES = {
    "priority": "review_priority_scores.csv",
    "anomaly": "anomaly_scores.csv",
    "peer_summary": "peer_benchmark_summary.csv",
    "duplicate_summary": "duplicate_summary.csv",
    "payment_summary": "payment_irregularity_summary.csv",
    "fund_progress": "fund_progress_evidence.csv",
    "compliance_summary": "compliance_summary.csv",
    "prediction": "predictive_scores.csv",
    "trend": "work_trend_context.csv",
    "features": "project_features.csv",
}

GROUP_TABLES = {
    "contributions": "review_priority_evidence.csv",
    "alerts": "review_alerts.csv",
    "peer_evidence": "peer_benchmark_evidence.csv",
    "payment_evidence": "payment_irregularities.csv",
    "compliance_evidence": "compliance_evidence.csv",
    "prediction_explanations": "predictive_explanations.csv",
}

_CHUNK_PATTERN = re.compile(r"MPLADS-2023-P\d{3}")
_PROHIBITED_ARTIFACT_TERMS = (
    "ground_truth",
    "expected_risk",
    "injected_anomaly",
    "detector_hotspots",
)


def _json_value(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if math.isnan(float(value)) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value.item() if hasattr(value, "item") else value


def _selected(record: dict[str, Any] | None, fields: list[str]) -> dict[str, Any]:
    if record is None:
        return {}
    return {field: _json_value(record.get(field)) for field in fields}


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {str(key): _json_value(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().casefold() == "true"
    return bool(value) if value is not None and not pd.isna(value) else False


class ArtifactRepository:
    """Read-only indexed view of governed Day 1--7 production artifacts."""

    def __init__(self, paths: ProjectPaths) -> None:
        self.paths = paths
        processed = paths.processed_data_dir
        self._single: dict[str, dict[str, dict[str, Any]]] = {}
        for name, filename in SINGLE_TABLES.items():
            frame = pd.read_csv(processed / filename, low_memory=False)
            if not frame["work_id"].is_unique:
                raise ValueError(f"{filename} must contain unique work rows")
            if name != "fund_progress" and len(frame) != 3_000:
                raise ValueError(f"{filename} must contain 3,000 unique work rows")
            self._single[name] = {
                str(row["work_id"]): row for row in frame.to_dict(orient="records")
            }

        self._groups: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for name, filename in GROUP_TABLES.items():
            frame = pd.read_csv(processed / filename, low_memory=False)
            grouped: dict[str, list[dict[str, Any]]] = {}
            for work_id, group in frame.groupby("work_id", sort=False, dropna=False):
                grouped[str(work_id)] = group.to_dict(orient="records")
            self._groups[name] = grouped

        duplicate_pairs = pd.read_csv(
            processed / "duplicate_candidates.csv", low_memory=False
        )
        duplicate_pairs = duplicate_pairs.loc[
            duplicate_pairs["review_candidate"].map(_truthy)
        ]
        self._duplicate_pairs: dict[str, list[dict[str, Any]]] = {}
        for row in duplicate_pairs.to_dict(orient="records"):
            for work_id in (str(row["work_id_a"]), str(row["work_id_b"])):
                self._duplicate_pairs.setdefault(work_id, []).append(row)

        self.day6_summary = json.loads(
            (processed / "day6_predictive_summary.json").read_text(encoding="utf-8")
        )
        self.work_ids = sorted(
            self._single["priority"],
            key=lambda item: int(self._single["priority"][item]["review_priority_rank_overall"]),
        )
        self._validate_source_boundary()

    def _validate_source_boundary(self) -> None:
        names = [*SINGLE_TABLES.values(), *GROUP_TABLES.values(), "duplicate_candidates.csv"]
        lowered = " ".join(names).casefold()
        if any(term in lowered for term in _PROHIBITED_ARTIFACT_TERMS):
            raise RuntimeError("Evidence repository includes a prohibited evaluation/helper artifact")

    def _one(self, name: str, work_id: str) -> dict[str, Any]:
        try:
            return self._single[name][work_id]
        except KeyError as exc:
            raise KeyError(f"Unknown work_id {work_id!r} in {name}") from exc

    def build_explanation_evidence(self, work_id: str) -> dict[str, Any]:
        """Build one read-only bundle; no score or compliance result is recalculated."""

        priority = self._one("priority", work_id)
        feature = self._one("features", work_id)
        contribution_rows = self._groups["contributions"].get(work_id, [])
        contribution_rows = sorted(
            contribution_rows,
            key=lambda row: (-float(row["contribution_points"]), str(row["family"])),
        )
        top_contributions = [
            _selected(
                row,
                [
                    "family",
                    "family_score_0_100",
                    "family_weight_pct",
                    "contribution_points",
                    "source_artifact",
                    "evidence_code",
                    "evidence_summary",
                    "data_available",
                    "applicable",
                ],
            )
            for row in contribution_rows
            if float(row["contribution_points"]) > 0
        ]

        alert_rows = self._groups["alerts"].get(work_id, [])
        alerts = [
            _selected(
                row,
                [
                    "alert_id",
                    "alert_type",
                    "evidence_code",
                    "alert_strength_0_100",
                    "alert_summary",
                    "source_artifact",
                    "source_record_reference",
                ],
            )
            for row in alert_rows
        ]

        anomaly = _selected(
            self._one("anomaly", work_id),
            [
                "lifecycle_stage",
                "within_stage_anomaly_percentile_0_100",
                "within_stage_rank",
                "stage_population",
                "peer_outlier_count",
                "max_abs_peer_deviation",
                "top_peer_deviation_metric",
            ],
        )
        anomaly["evidence_code"] = "LIFECYCLE_ANOMALY_PERCENTILE"
        anomaly["interpretation"] = "Statistical unusualness within lifecycle; not a probability."

        peer_rows = self._groups["peer_evidence"].get(work_id, [])
        peer_rows = sorted(
            peer_rows,
            key=lambda row: -abs(float(row.get("absolute_robust_deviation", 0) or 0)),
        )[:3]
        peers = []
        for row in peer_rows:
            selected = _selected(
                row,
                [
                    "metric",
                    "observed_value",
                    "peer_median",
                    "peer_mad",
                    "peer_iqr",
                    "robust_deviation",
                    "absolute_robust_deviation",
                    "deviation_method",
                    "peer_group_level",
                    "peer_group_size",
                    "statistical_peer_outlier",
                    "direction",
                ],
            )
            selected["evidence_code"] = f"PEER_DEVIATION:{row['metric']}"
            peers.append(selected)

        duplicate_rows = sorted(
            self._duplicate_pairs.get(work_id, []),
            key=lambda row: -float(row["duplicate_similarity_score_0_100"]),
        )[:5]
        duplicates = []
        for row in duplicate_rows:
            paired = row["work_id_b"] if str(row["work_id_a"]) == work_id else row["work_id_a"]
            selected = _selected(
                row,
                [
                    "pair_id",
                    "duplicate_similarity_score_0_100",
                    "text_cosine_similarity",
                    "geographic_distance_km",
                    "amount_similarity",
                    "recommendation_date_difference_days",
                    "same_district",
                    "same_block",
                    "same_village",
                    "sector_match",
                    "sub_sector_match",
                    "review_policy_reason",
                    "evidence_summary",
                ],
            )
            selected["paired_work_id"] = str(paired)
            selected["review_candidate"] = True
            selected["evidence_code"] = f"DUPLICATE_REVIEW:{row['pair_id']}"
            duplicates.append(selected)

        payment_rows = self._groups["payment_evidence"].get(work_id, [])
        payments = [
            _selected(
                row,
                [
                    "payment_id",
                    "signal_code",
                    "signal_severity",
                    "observed_value",
                    "expected_pattern",
                    "evidence",
                    "event_date",
                ],
            )
            for row in payment_rows
        ]
        fund = _selected(
            self._single["fund_progress"].get(work_id),
            [
                "payment_based_financial_progress_pct_as_of",
                "latest_reported_financial_progress_pct_as_of",
                "latest_physical_progress_pct_as_of",
                "fund_minus_physical_gap_pct_as_of",
                "latest_historical_financial_minus_physical_gap_pct",
                "max_historical_financial_minus_physical_gap_pct",
                "large_gap_report_count",
                "latest_consecutive_large_gap_reports",
                "current_large_positive_fund_gap_review_heuristic",
                "persistent_large_reported_gap_review_heuristic",
                "status_not_started_with_payment_evidence",
                "status_not_started_with_physical_progress",
                "evidence_interpretation",
            ],
        )

        compliance_rows = [
            row
            for row in self._groups["compliance_evidence"].get(work_id, [])
            if str(row.get("result")) in {"REVIEW", "NON_COMPLIANT"}
        ]
        compliance = []
        direct_chunk_ids: list[str] = []
        for row in compliance_rows:
            chunks = _CHUNK_PATTERN.findall(str(row.get("guideline_chunk_ids", "")))
            direct_chunk_ids.extend(chunks)
            selected = _selected(
                row,
                [
                    "rule_id",
                    "rule_title",
                    "rule_category",
                    "result",
                    "severity",
                    "observed_value",
                    "expected_condition",
                    "evidence",
                    "guideline_version",
                    "guideline_chapter",
                    "guideline_clause",
                    "guideline_page",
                    "guideline_printed_page",
                    "official_reference",
                    "as_of_date",
                ],
            )
            selected["guideline_chunk_ids"] = chunks
            compliance.append(selected)

        prediction_row = self._one("prediction", work_id)
        prediction_explanations = []
        for row in self._groups["prediction_explanations"].get(work_id, []):
            prediction_explanations.append(
                _selected(
                    row,
                    [
                        "prediction_target",
                        "model_output_explained",
                        "serving_score_field",
                        "explanation_scope",
                        "top_feature_1",
                        "top_feature_1_value",
                        "top_feature_1_shap",
                        "top_feature_2",
                        "top_feature_2_value",
                        "top_feature_2_shap",
                        "top_feature_3",
                        "top_feature_3_value",
                        "top_feature_3_shap",
                    ],
                )
            )
        prediction = _selected(
            prediction_row,
            [
                "cost_overrun_prediction_applicability",
                "already_over_sanction_as_of",
                "cost_overrun_model_score_raw_probability",
                "cost_overrun_calibration_status",
                "cost_overrun_calibration_serving_eligible",
                "cost_overrun_model_quality_status",
                "cost_overrun_serving_score",
                "cost_overrun_serving_percentile_0_100",
                "cost_overrun_serving_rank",
            ],
        )
        prediction["calibrated_probability_used_as_serving_evidence"] = False
        prediction["shap_contributors"] = prediction_explanations
        prediction["delay_model"] = {
            "available": False,
            "status": self.day6_summary["delay_serving_status"],
            "negative_work_count": self.day6_summary["delay_model_feasibility"][
                "negative_work_count"
            ],
            "minimum_required": self.day6_summary["delay_model_feasibility"][
                "minimum_negative_work_count"
            ],
        }

        evidence_codes = list(
            dict.fromkeys(
                [str(row["evidence_code"]) for row in top_contributions]
                + [str(row["evidence_code"]) for row in alerts]
                + [anomaly["evidence_code"]]
                + [str(row["evidence_code"]) for row in peers]
                + [str(row["evidence_code"]) for row in duplicates]
                + [str(row["signal_code"]) for row in payments]
                + [str(row["rule_id"]) for row in compliance]
                + ["COST_OVERRUN_SERVING_PERCENTILE"]
                + ["DELAY_MODEL_UNAVAILABLE"]
                + ["OPERATIONAL_TREND_CONTEXT"]
                + (["ALREADY_OVERDUE_AS_OF"] if _truthy(priority["already_overdue_as_of"]) else [])
                + (["ALREADY_OVER_SANCTION_AS_OF"] if _truthy(priority["already_over_sanction_as_of"]) else [])
            )
        )

        bundle = {
            "work_id": work_id,
            "lifecycle_stage": str(priority["lifecycle_stage"]),
            "project_context_untrusted_data": _selected(
                feature,
                [
                    "state_name",
                    "district",
                    "sector",
                    "sub_sector",
                    "sanction_status",
                    "recommended_amount_inr",
                    "sanctioned_amount_inr",
                ],
            ),
            "review_priority": _selected(
                priority,
                [
                    "review_priority_score_0_100",
                    "review_priority_band",
                    "review_priority_rank_overall",
                    "review_priority_rank_within_lifecycle",
                    "fusion_evidence_coverage_pct",
                ],
            ),
            "top_contributions": top_contributions,
            "alerts": alerts,
            "anomaly": anomaly,
            "peer": {
                "summary": _selected(
                    self._one("peer_summary", work_id),
                    [
                        "peer_metric_count",
                        "peer_outlier_count",
                        "max_abs_peer_deviation",
                        "top_peer_deviation_metric",
                        "top_peer_deviation_value",
                    ],
                ),
                "strongest_deviations": peers,
            },
            "duplicate": {
                "summary": _selected(
                    self._one("duplicate_summary", work_id),
                    [
                        "review_candidate_count",
                        "best_review_candidate_work_id",
                        "best_review_similarity_score_0_100",
                        "review_candidate",
                    ],
                ),
                "review_candidates_only": duplicates,
            },
            "payment_execution": {
                "summary": _selected(
                    self._one("payment_summary", work_id),
                    [
                        "payment_irregularity_evidence_count",
                        "has_payment_irregularity_evidence",
                    ],
                ),
                "selected_evidence": payments,
                "fund_progress_context": fund,
            },
            "observed_conditions": {
                "already_overdue_as_of": _truthy(priority["already_overdue_as_of"]),
                "already_over_sanction_as_of": _truthy(
                    priority["already_over_sanction_as_of"]
                ),
                "overdue_days_as_of": _json_value(feature.get("overdue_days_as_of")),
                "financial_overrun_amount_inr_as_of": _json_value(
                    feature.get("financial_overrun_amount_inr_as_of")
                ),
            },
            "compliance": {
                "summary": _selected(
                    self._one("compliance_summary", work_id),
                    [
                        "rules_review_count",
                        "rules_non_compliant_count",
                        "highest_compliance_evidence_severity",
                        "top_compliance_rule_id",
                    ],
                ),
                "actionable_findings": compliance,
                "direct_chunk_ids": list(dict.fromkeys(direct_chunk_ids)),
            },
            "prediction": prediction,
            "trend": _selected(
                self._one("trend", work_id),
                [
                    "selected_trend_group",
                    "selected_trend_group_value",
                    "strongest_operational_trend_metric",
                    "strongest_operational_trend_robust_z",
                    "operational_trend_deviation_flag",
                    "operational_trend_context_score_0_100",
                ],
            ),
            "allowed_evidence_codes": evidence_codes,
            "governance": {
                "priority_read_not_recalculated": True,
                "detector_hotspots_used": False,
                "evaluation_or_helper_artifacts_used": False,
                "only_day4_1_review_candidates_explained": True,
            },
        }
        serialized = json.dumps(bundle, ensure_ascii=False).casefold()
        if any(term in serialized for term in _PROHIBITED_ARTIFACT_TERMS[:3]):
            raise RuntimeError("Evidence bundle contains a prohibited evaluation/helper field")
        return bundle


def build_explanation_evidence(
    work_id: str, paths: ProjectPaths | None = None
) -> dict[str, Any]:
    return ArtifactRepository(paths or ProjectPaths.discover()).build_explanation_evidence(
        work_id
    )
