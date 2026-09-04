"""Build and persist the leakage-aware Day-2 project feature snapshot."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from intelligence.data.config import load_settings
from intelligence.data.loader import OperationalDataBundle, load_operational_data
from intelligence.data.paths import ProjectPaths

from .aggregations import (
    aggregate_assets_as_of,
    aggregate_payments_as_of,
    aggregate_progress_as_of,
    safe_ratio,
)
from .catalog import build_feature_catalog, feature_catalog_payload, feature_column_names


COUNT_COLUMNS = [
    "released_payment_count_as_of",
    "released_payment_total_inr_as_of",
    "unique_vendor_count_as_of",
    "final_payment_count_as_of",
    "zero_value_released_payment_count_as_of",
    "progress_report_count_as_of",
    "physical_progress_decrease_count_as_of",
    "same_day_progress_extra_count_as_of",
    "asset_record_count_as_of",
]

BOOLEAN_COLUMNS = [
    "has_final_payment_as_of",
    "is_completed_as_of",
    "completion_marked_as_of",
    "uc_recorded_as_of",
    "handover_recorded_as_of",
    "public_use_recorded_as_of",
    "audit_recorded_as_of",
]

FORBIDDEN_FEATURE_NAMES = {
    "duplicate_group_reference",
    "payment_id",
    "progress_id",
    "asset_id",
    "vendor_id",
    "payment_release_date",
    "report_date",
}
FORBIDDEN_FEATURE_FRAGMENTS = (
    "injected_anomaly",
    "expected_risk",
    "ground_truth",
)


def _merge_one_row_per_work(base: pd.DataFrame, aggregate: pd.DataFrame) -> pd.DataFrame:
    if aggregate["work_id"].duplicated().any():
        raise ValueError("One-to-many aggregate contains duplicate work_id values")
    before = len(base)
    merged = base.merge(aggregate, on="work_id", how="left", validate="one_to_one")
    if len(merged) != before:
        raise ValueError("One-row-per-work cardinality changed during aggregate join")
    return merged


def build_project_features(
    bundle: OperationalDataBundle,
    as_of_date: date,
) -> pd.DataFrame:
    """Create exactly one leakage-aware snapshot row per work.

    Payment, progress, and asset histories are independently filtered and
    aggregated before any one-to-one join to the work spine.
    """

    as_of = pd.Timestamp(as_of_date)
    works = bundle.works
    sanction_known = works["sanction_date"].notna() & works["sanction_date"].le(as_of)
    actual_start_known = works["actual_start_date"].notna() & works["actual_start_date"].le(as_of)

    features = pd.DataFrame(
        {
            "work_id": works["work_id"],
            "mp_id": works["mp_id"],
            "state_name": works["state_name"],
            "constituency": works["constituency"],
            "district": works["district"],
            "sector": works["sector"],
            "sub_sector": works["sub_sector"],
            "implementing_agency_id": works["implementing_agency_id"],
            "sanction_status": works["sanction_status"],
            "source_current_status": works["current_status"],
            "feature_snapshot_date": as_of,
            "is_rejected": works["sanction_status"].eq("Rejected"),
            "recommendation_date": works["recommendation_date"],
            "sanction_date_as_of": works["sanction_date"].where(sanction_known),
            "expected_start_date": works["expected_start_date"],
            "expected_completion_date": works["expected_completion_date"],
            "actual_start_date_as_of": works["actual_start_date"].where(actual_start_known),
            "recommended_amount_inr": works["recommended_amount_inr"],
            "technical_estimate_amount_inr": works["technical_estimate_amount_inr"],
            "sanctioned_amount_inr": works["sanctioned_amount_inr"].where(sanction_known),
            "source_current_physical_progress_pct": works[
                "current_physical_progress_pct"
            ],
            "source_current_expenditure_inr": works["current_expenditure_inr"],
        }
    )

    payment_aggregates = aggregate_payments_as_of(bundle.payments, as_of_date)
    progress_aggregates = aggregate_progress_as_of(bundle.progress, as_of_date)
    asset_aggregates = aggregate_assets_as_of(bundle.assets, as_of_date)
    for aggregate in (payment_aggregates, progress_aggregates, asset_aggregates):
        features = _merge_one_row_per_work(features, aggregate)

    for column in COUNT_COLUMNS:
        features[column] = features[column].fillna(0).astype("int64")
    for column in BOOLEAN_COLUMNS:
        features[column] = features[column].astype("boolean").fillna(False).astype(bool)
    features["max_physical_progress_drop_pct_as_of"] = features[
        "max_physical_progress_drop_pct_as_of"
    ].fillna(0.0)

    features["estimate_to_recommended_ratio"] = safe_ratio(
        features["technical_estimate_amount_inr"], features["recommended_amount_inr"]
    )
    features["sanction_to_recommended_ratio"] = safe_ratio(
        features["sanctioned_amount_inr"], features["recommended_amount_inr"]
    )
    features["sanction_to_estimate_ratio"] = safe_ratio(
        features["sanctioned_amount_inr"], features["technical_estimate_amount_inr"]
    )
    features["days_recommendation_to_sanction"] = (
        features["sanction_date_as_of"] - features["recommendation_date"]
    ).dt.days
    features["planned_duration_days"] = (
        features["expected_completion_date"] - features["expected_start_date"]
    ).dt.days
    features["days_sanction_to_expected_start"] = (
        features["expected_start_date"] - features["sanction_date_as_of"]
    ).dt.days

    features["expenditure_to_sanction_pct_as_of"] = safe_ratio(
        features["released_payment_total_inr_as_of"], features["sanctioned_amount_inr"]
    ) * 100.0
    positive_sanction = features["sanctioned_amount_inr"].gt(0)
    overrun = (
        features["released_payment_total_inr_as_of"] - features["sanctioned_amount_inr"]
    ).clip(lower=0)
    features["financial_overrun_amount_inr_as_of"] = overrun.where(positive_sanction)
    features["financial_overrun_pct_as_of"] = (
        safe_ratio(overrun, features["sanctioned_amount_inr"]) * 100.0
    )

    features["actual_start_available_as_of"] = features[
        "actual_start_date_as_of"
    ].notna()
    features["days_since_actual_start_as_of"] = (
        as_of - features["actual_start_date_as_of"]
    ).dt.days
    features["days_to_expected_completion_as_of"] = (
        features["expected_completion_date"] - as_of
    ).dt.days
    overdue = (as_of - features["expected_completion_date"]).dt.days.clip(lower=0)
    features["overdue_days_as_of"] = overdue.where(~features["is_completed_as_of"])
    elapsed_from_plan = (as_of - features["expected_start_date"]).dt.days.clip(lower=0)
    features["schedule_elapsed_ratio_as_of"] = safe_ratio(
        elapsed_from_plan, features["planned_duration_days"]
    )

    features["actual_duration_days"] = (
        features["completion_date_as_of"] - features["actual_start_date_as_of"]
    ).dt.days
    features["completion_delay_days"] = (
        features["completion_date_as_of"] - features["expected_completion_date"]
    ).dt.days

    features["source_vs_asof_expenditure_difference_inr"] = (
        features["source_current_expenditure_inr"]
        - features["released_payment_total_inr_as_of"]
    )
    features["source_vs_asof_physical_progress_difference_pct"] = (
        features["source_current_physical_progress_pct"]
        - features["latest_physical_progress_pct_as_of"]
    )

    sanctioned_as_of = sanction_known & works["sanction_status"].eq("Sanctioned")
    lifecycle = pd.Series("EXECUTION", index=features.index, dtype="string")
    lifecycle = lifecycle.mask(features["is_completed_as_of"], "COMPLETION")
    lifecycle = lifecycle.mask(features["is_rejected"] | ~sanctioned_as_of, "PRE_SANCTION")
    features["lifecycle_stage"] = lifecycle

    ordered_columns = feature_column_names()
    missing = [column for column in ordered_columns if column not in features]
    extra = [column for column in features if column not in ordered_columns]
    if missing or extra:
        raise ValueError(f"Feature contract mismatch: missing={missing}, extra={extra}")
    features = features[ordered_columns]
    validate_project_features(features, bundle, as_of_date)
    return features


def build_feature_diagnostics(
    bundle: OperationalDataBundle,
    features: pd.DataFrame,
    as_of_date: date,
) -> dict[str, Any]:
    as_of = pd.Timestamp(as_of_date)
    released = bundle.payments["payment_status"].eq("Released")
    included_payments = released & bundle.payments["payment_release_date"].le(as_of)
    future_payments = released & bundle.payments["payment_release_date"].gt(as_of)
    included_progress = bundle.progress["report_date"].le(as_of)
    asset_events = {
        field: int(bundle.assets[field].gt(as_of).sum())
        for field in [
            "completion_date",
            "completion_marked_date",
            "utilization_certificate_date",
            "handover_date",
            "public_use_date",
            "audit_date",
        ]
    }
    catalog = build_feature_catalog()
    return {
        "as_of_date": as_of_date.isoformat(),
        "feature_rows": len(features),
        "feature_columns": len(features.columns),
        "model_eligible_feature_count": sum(bool(item["model_eligible"]) for item in catalog),
        "generic_anomaly_eligible_feature_count": sum(
            bool(item["generic_anomaly_eligible"]) for item in catalog
        ),
        "payment_rows_included_as_of": int(included_payments.sum()),
        "payment_value_inr_included_as_of": int(
            bundle.payments.loc[included_payments, "payment_amount_inr"].sum()
        ),
        "future_payment_release_rows_excluded": int(future_payments.sum()),
        "future_payment_release_value_inr_excluded": int(
            bundle.payments.loc[future_payments, "payment_amount_inr"].sum()
        ),
        "progress_rows_included_as_of": int(included_progress.sum()),
        "future_progress_rows_excluded": int((~included_progress).sum()),
        "works_with_zero_progress_reports_as_of": int(
            features["progress_report_count_as_of"].eq(0).sum()
        ),
        "works_completed_as_of": int(features["is_completed_as_of"].sum()),
        "future_asset_events_excluded": asset_events,
        "lifecycle_stage_counts": {
            str(key): int(value)
            for key, value in features["lifecycle_stage"].value_counts().items()
        },
    }


def validate_project_features(
    features: pd.DataFrame,
    bundle: OperationalDataBundle,
    as_of_date: date,
) -> dict[str, Any]:
    """Fail fast when the one-row, leakage, or as-of contracts are violated."""

    problems: list[str] = []
    expected_ids = set(bundle.works["work_id"])
    if len(features) != 3_000 or len(features) != len(bundle.works):
        problems.append(f"expected 3000 work rows, found {len(features)}")
    if features["work_id"].isna().any():
        problems.append("work_id contains nulls")
    if features["work_id"].duplicated().any():
        problems.append("work_id is not unique")
    if set(features["work_id"]) != expected_ids:
        problems.append("feature work_id set differs from the operational work spine")

    forbidden_exact = FORBIDDEN_FEATURE_NAMES.intersection(features.columns)
    forbidden_fragments = [
        column
        for column in features.columns
        if any(fragment in column.lower() for fragment in FORBIDDEN_FEATURE_FRAGMENTS)
    ]
    if forbidden_exact or forbidden_fragments:
        problems.append(
            f"forbidden leakage/history columns present: {sorted(forbidden_exact)}"
            f"{sorted(forbidden_fragments)}"
        )

    numeric = features.select_dtypes(include=["number"])
    if np.isinf(numeric.to_numpy(dtype="float64", na_value=np.nan)).any():
        problems.append("numeric feature table contains infinite values")

    ratio_denominators = {
        "estimate_to_recommended_ratio": features["recommended_amount_inr"],
        "sanction_to_recommended_ratio": features["recommended_amount_inr"],
        "sanction_to_estimate_ratio": features["technical_estimate_amount_inr"],
        "expenditure_to_sanction_pct_as_of": features["sanctioned_amount_inr"],
        "financial_overrun_pct_as_of": features["sanctioned_amount_inr"],
        "schedule_elapsed_ratio_as_of": features["planned_duration_days"],
    }
    for ratio, denominator in ratio_denominators.items():
        if features.loc[denominator.le(0) | denominator.isna(), ratio].notna().any():
            problems.append(f"{ratio} is populated where its denominator is unavailable")

    as_of = pd.Timestamp(as_of_date)
    for column in [
        "sanction_date_as_of",
        "actual_start_date_as_of",
        "first_payment_release_date_as_of",
        "last_payment_release_date_as_of",
        "first_progress_report_date_as_of",
        "latest_progress_report_date_as_of",
        "completion_date_as_of",
    ]:
        if features[column].gt(as_of).any():
            problems.append(f"{column} contains an event after AS_OF_DATE")

    expected_payment_total = (
        bundle.payments.loc[
            bundle.payments["payment_status"].eq("Released")
            & bundle.payments["payment_release_date"].le(as_of)
        ]
        .groupby("work_id")["payment_amount_inr"]
        .sum()
    )
    reconciled_payment_total = features["work_id"].map(expected_payment_total).fillna(0)
    if not features["released_payment_total_inr_as_of"].eq(reconciled_payment_total).all():
        problems.append("as-of released payment totals do not reconcile")

    expected_completed = set(
        bundle.assets.loc[bundle.assets["completion_date"].le(as_of), "work_id"]
    )
    actual_completed = set(features.loc[features["is_completed_as_of"], "work_id"])
    if expected_completed != actual_completed:
        problems.append("completion flags do not obey completion_date <= AS_OF_DATE")

    catalog_names = [item["name"] for item in build_feature_catalog()]
    if catalog_names != features.columns.tolist():
        problems.append("feature catalog does not exactly cover output columns in order")
    if problems:
        raise ValueError("; ".join(problems))
    return {
        "row_count": len(features),
        "column_count": len(features.columns),
        "unique_work_ids": int(features["work_id"].nunique()),
        "status": "PASS",
    }


def write_feature_outputs(
    features: pd.DataFrame,
    paths: ProjectPaths,
    as_of_date: date,
) -> tuple[Path, Path]:
    output_dir = paths.ensure_processed_data_dir().resolve()
    expected = (paths.project_root / "data" / "processed").resolve()
    if output_dir != expected:
        raise ValueError(f"Feature outputs must use {expected}, not {output_dir}")

    feature_path = output_dir / "project_features.csv"
    catalog_path = output_dir / "feature_catalog.json"
    features.to_csv(feature_path, index=False, encoding="utf-8", date_format="%Y-%m-%d")

    payload = feature_catalog_payload(as_of_date)
    catalog_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return feature_path, catalog_path


def main() -> int:
    paths = ProjectPaths.discover()
    settings = load_settings(paths)
    bundle = load_operational_data(paths)
    features = build_project_features(bundle, settings.as_of_date)
    feature_path, catalog_path = write_feature_outputs(features, paths, settings.as_of_date)
    diagnostics = build_feature_diagnostics(bundle, features, settings.as_of_date)
    print(f"Project features: {feature_path}")
    print(f"Feature catalog: {catalog_path}")
    print(json.dumps(diagnostics, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
