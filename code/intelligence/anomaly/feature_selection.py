"""Unlabeled, lifecycle-specific feature selection for Day 3."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd


LIFECYCLE_STAGES = ("PRE_SANCTION", "EXECUTION", "COMPLETION")
MISSING_PERCENTAGE_LIMIT = 50.0
NEAR_ZERO_DOMINANT_PERCENTAGE = 99.0

PRE_SANCTION_FEATURES = (
    "recommended_amount_inr",
    "technical_estimate_amount_inr",
    "estimate_to_recommended_ratio",
)

EXECUTION_FEATURES = (
    "recommended_amount_inr",
    "technical_estimate_amount_inr",
    "sanctioned_amount_inr",
    "estimate_to_recommended_ratio",
    "sanction_to_recommended_ratio",
    "sanction_to_estimate_ratio",
    "days_recommendation_to_sanction",
    "planned_duration_days",
    "days_sanction_to_expected_start",
    "released_payment_count_as_of",
    "released_payment_total_inr_as_of",
    "largest_payment_inr_as_of",
    "mean_payment_inr_as_of",
    "largest_payment_share_as_of",
    "days_since_last_payment_as_of",
    "expenditure_to_sanction_pct_as_of",
    "financial_overrun_amount_inr_as_of",
    "financial_overrun_pct_as_of",
    "progress_report_count_as_of",
    "latest_physical_progress_pct_as_of",
    "latest_financial_progress_pct_as_of",
    "latest_expected_progress_pct_as_of",
    "financial_minus_physical_gap_pct_as_of",
    "expected_minus_physical_gap_pct_as_of",
    "physical_progress_decrease_count_as_of",
    "max_physical_progress_drop_pct_as_of",
    "physical_progress_velocity_pct_per_30d",
    "actual_start_available_as_of",
    "days_since_actual_start_as_of",
    "days_to_expected_completion_as_of",
    "overdue_days_as_of",
    "schedule_elapsed_ratio_as_of",
)

# Completion uses only current as-of financial, payment, progress, and schedule
# evidence from the generic pool. Synthetic completion-date, closure-routing,
# reconciliation, and compliance-only fields never enter this list.
COMPLETION_FEATURES = EXECUTION_FEATURES

STAGE_DOMAIN_FEATURES: Mapping[str, tuple[str, ...]] = {
    "PRE_SANCTION": PRE_SANCTION_FEATURES,
    "EXECUTION": EXECUTION_FEATURES,
    "COMPLETION": COMPLETION_FEATURES,
}


def _catalog_records(catalog: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    records = catalog.get("features") if isinstance(catalog, Mapping) else catalog
    if not isinstance(records, Sequence):
        raise ValueError("Feature catalog must contain a features sequence")
    return list(records)


def _series_profile(series: pd.Series) -> dict[str, Any]:
    values = series.dropna()
    non_null_count = int(len(values))
    unique_count = int(values.nunique(dropna=True))
    counts = values.value_counts(dropna=False)
    dominant_percentage = (
        float(100.0 * counts.iloc[0] / non_null_count) if non_null_count else None
    )
    return {
        "non_null_count": non_null_count,
        "missing_percentage": round(
            100.0 * (len(series) - non_null_count) / max(1, len(series)), 6
        ),
        "unique_count": unique_count,
        "dominant_value_percentage": (
            round(dominant_percentage, 6)
            if dominant_percentage is not None
            else None
        ),
    }


def select_lifecycle_feature_sets(
    features: pd.DataFrame,
    catalog: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Select stage features without labels, targets, or evaluation data.

    The generic catalog flag is only an admission pool. Domain applicability is
    evaluated first, followed by stage-local missingness and distribution checks.
    """

    if "lifecycle_stage" not in features or "work_id" not in features:
        raise ValueError("Feature table lacks required lifecycle routing columns")

    records = _catalog_records(catalog)
    generic_candidates = [
        str(item["name"])
        for item in records
        if bool(item.get("generic_anomaly_eligible", False))
    ]
    missing_columns = sorted(set(generic_candidates).difference(features.columns))
    if missing_columns:
        raise ValueError(f"Generic candidates missing from feature table: {missing_columns}")

    result: dict[str, Any] = {
        "candidate_policy": "catalog generic_anomaly_eligible == true",
        "generic_candidate_count": len(generic_candidates),
        "generic_candidates": generic_candidates,
        "missing_percentage_exclusion_rule": "> 50% within lifecycle stage",
        "near_zero_variance_rule": (
            "non-constant feature with one non-null value representing at least 99% "
            "of stage observations"
        ),
        "ground_truth_used_for_selection": False,
        "stages": {},
    }

    observed_stages = set(features["lifecycle_stage"].dropna().astype(str))
    if observed_stages != set(LIFECYCLE_STAGES):
        raise ValueError(f"Expected exactly {LIFECYCLE_STAGES}; observed {sorted(observed_stages)}")

    for stage in LIFECYCLE_STAGES:
        stage_rows = features.loc[features["lifecycle_stage"].eq(stage)]
        domain_allowed = set(STAGE_DOMAIN_FEATURES[stage])
        selected: list[str] = []
        excluded: list[dict[str, Any]] = []
        profiles: dict[str, dict[str, Any]] = {}

        for name in generic_candidates:
            profile = _series_profile(stage_rows[name])
            profiles[name] = profile
            if name not in domain_allowed:
                excluded.append(
                    {
                        "feature": name,
                        "reason": "STRUCTURALLY_INAPPLICABLE_TO_LIFECYCLE",
                        **profile,
                    }
                )
            elif profile["missing_percentage"] > MISSING_PERCENTAGE_LIMIT:
                excluded.append(
                    {
                        "feature": name,
                        "reason": "EXCESSIVE_STAGE_MISSINGNESS",
                        **profile,
                    }
                )
            elif profile["unique_count"] <= 1:
                excluded.append(
                    {
                        "feature": name,
                        "reason": "ZERO_VARIANCE_WITHIN_STAGE",
                        **profile,
                    }
                )
            elif (
                profile["dominant_value_percentage"] is not None
                and profile["dominant_value_percentage"]
                >= NEAR_ZERO_DOMINANT_PERCENTAGE
            ):
                excluded.append(
                    {
                        "feature": name,
                        "reason": "NEAR_ZERO_VARIANCE_WITHIN_STAGE",
                        **profile,
                    }
                )
            else:
                selected.append(name)

        if not selected:
            raise ValueError(f"No usable unlabeled features remain for {stage}")
        result["stages"][stage] = {
            "row_count": int(len(stage_rows)),
            "domain_allowed_features": [
                name for name in generic_candidates if name in domain_allowed
            ],
            "selected_feature_count": len(selected),
            "selected_features": selected,
            "excluded_feature_count": len(excluded),
            "excluded_features": excluded,
            "stage_profiles": profiles,
        }

    return result
