"""Independent as-of aggregations for one-to-many lifecycle histories."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd


PAYMENT_AGGREGATE_COLUMNS = [
    "work_id",
    "released_payment_count_as_of",
    "released_payment_total_inr_as_of",
    "unique_vendor_count_as_of",
    "largest_payment_inr_as_of",
    "mean_payment_inr_as_of",
    "largest_payment_share_as_of",
    "vendor_hhi_as_of",
    "first_payment_release_date_as_of",
    "last_payment_release_date_as_of",
    "days_since_last_payment_as_of",
    "final_payment_count_as_of",
    "has_final_payment_as_of",
    "zero_value_released_payment_count_as_of",
]

PROGRESS_AGGREGATE_COLUMNS = [
    "work_id",
    "progress_report_count_as_of",
    "first_progress_report_date_as_of",
    "latest_progress_report_date_as_of",
    "latest_physical_progress_pct_as_of",
    "latest_financial_progress_pct_as_of",
    "latest_expected_progress_pct_as_of",
    "financial_minus_physical_gap_pct_as_of",
    "expected_minus_physical_gap_pct_as_of",
    "days_since_last_progress_report_as_of",
    "physical_progress_decrease_count_as_of",
    "max_physical_progress_drop_pct_as_of",
    "same_day_progress_extra_count_as_of",
    "physical_progress_velocity_pct_per_30d",
]

ASSET_AGGREGATE_COLUMNS = [
    "work_id",
    "asset_record_count_as_of",
    "is_completed_as_of",
    "completion_date_as_of",
    "completion_marked_as_of",
    "uc_recorded_as_of",
    "handover_recorded_as_of",
    "public_use_recorded_as_of",
    "audit_recorded_as_of",
    "final_expenditure_inr_as_of",
]

ASSET_EVENT_DATE_COLUMNS = [
    "completion_date",
    "completion_marked_date",
    "utilization_certificate_date",
    "handover_date",
    "public_use_date",
    "audit_date",
]


def natural_payment_stage(payment_stage: pd.Series) -> pd.Series:
    """Parse the audited natural sequence from values such as ``Stage 10``."""

    return pd.to_numeric(
        payment_stage.astype("string").str.extract(r"^Stage\s+(\d+)$", expand=False),
        errors="coerce",
    ).astype("Int64")


def released_payments_as_of(payments: pd.DataFrame, as_of_date: date) -> pd.DataFrame:
    """Return released rows visible by the snapshot in canonical Day-1.1 order."""

    as_of = pd.Timestamp(as_of_date)
    visible = payments.loc[
        payments["payment_status"].eq("Released")
        & payments["payment_release_date"].le(as_of)
    ].copy()
    visible["_payment_stage_sequence"] = natural_payment_stage(visible["payment_stage"])
    visible = visible.sort_values(
        [
            "work_id",
            "payment_release_date",
            "_payment_stage_sequence",
            "payment_id",
        ],
        kind="stable",
        na_position="last",
    )
    return visible.drop(columns="_payment_stage_sequence")


def aggregate_payments_as_of(payments: pd.DataFrame, as_of_date: date) -> pd.DataFrame:
    """Aggregate released payments to one row per represented work."""

    visible = released_payments_as_of(payments, as_of_date)
    if visible.empty:
        return pd.DataFrame(columns=PAYMENT_AGGREGATE_COLUMNS)

    grouped = visible.groupby("work_id", sort=False)
    result = grouped.agg(
        released_payment_count_as_of=("payment_id", "size"),
        released_payment_total_inr_as_of=("payment_amount_inr", "sum"),
        unique_vendor_count_as_of=("vendor_id", "nunique"),
        largest_payment_inr_as_of=("payment_amount_inr", "max"),
        mean_payment_inr_as_of=("payment_amount_inr", "mean"),
        first_payment_release_date_as_of=("payment_release_date", "first"),
        last_payment_release_date_as_of=("payment_release_date", "last"),
        final_payment_count_as_of=("is_final_payment", "sum"),
    ).reset_index()

    total = result["released_payment_total_inr_as_of"].astype("float64")
    result["largest_payment_share_as_of"] = (
        result["largest_payment_inr_as_of"].astype("float64") / total.where(total.gt(0))
    )

    vendor_totals = visible.groupby(["work_id", "vendor_id"])["payment_amount_inr"].sum()
    vendor_denominator = vendor_totals.groupby(level=0).transform("sum").where(lambda x: x.gt(0))
    vendor_hhi = (vendor_totals / vendor_denominator).pow(2).groupby(level=0).sum(min_count=1)
    result["vendor_hhi_as_of"] = result["work_id"].map(vendor_hhi)

    as_of = pd.Timestamp(as_of_date)
    result["days_since_last_payment_as_of"] = (
        as_of - result["last_payment_release_date_as_of"]
    ).dt.days
    result["final_payment_count_as_of"] = result["final_payment_count_as_of"].astype("int64")
    result["has_final_payment_as_of"] = result["final_payment_count_as_of"].gt(0)
    zero_counts = visible["payment_amount_inr"].eq(0).groupby(visible["work_id"]).sum()
    result["zero_value_released_payment_count_as_of"] = (
        result["work_id"].map(zero_counts).fillna(0).astype("int64")
    )
    return result[PAYMENT_AGGREGATE_COLUMNS]


def progress_reports_as_of(progress: pd.DataFrame, as_of_date: date) -> pd.DataFrame:
    """Return progress observations visible at the snapshot in stable report order."""

    visible = progress.loc[progress["report_date"].le(pd.Timestamp(as_of_date))].copy()
    return visible.sort_values(["work_id", "report_date", "progress_id"], kind="stable")


def aggregate_progress_as_of(progress: pd.DataFrame, as_of_date: date) -> pd.DataFrame:
    """Aggregate observed progress to one row per represented work without interpolation."""

    visible = progress_reports_as_of(progress, as_of_date)
    if visible.empty:
        return pd.DataFrame(columns=PROGRESS_AGGREGATE_COLUMNS)

    grouped = visible.groupby("work_id", sort=False)
    result = grouped.agg(
        progress_report_count_as_of=("progress_id", "size"),
        first_progress_report_date_as_of=("report_date", "first"),
        latest_progress_report_date_as_of=("report_date", "last"),
        latest_physical_progress_pct_as_of=("physical_progress_pct", "last"),
        latest_financial_progress_pct_as_of=("financial_progress_pct", "last"),
        latest_expected_progress_pct_as_of=("expected_progress_pct_by_date", "last"),
    ).reset_index()

    result["financial_minus_physical_gap_pct_as_of"] = (
        result["latest_financial_progress_pct_as_of"]
        - result["latest_physical_progress_pct_as_of"]
    )
    result["expected_minus_physical_gap_pct_as_of"] = (
        result["latest_expected_progress_pct_as_of"]
        - result["latest_physical_progress_pct_as_of"]
    )
    result["days_since_last_progress_report_as_of"] = (
        pd.Timestamp(as_of_date) - result["latest_progress_report_date_as_of"]
    ).dt.days

    previous = grouped["physical_progress_pct"].shift()
    change = visible["physical_progress_pct"] - previous
    decrease = change.lt(0)
    decrease_counts = decrease.groupby(visible["work_id"]).sum()
    maximum_drop = (-change.where(decrease)).groupby(visible["work_id"]).max()
    result["physical_progress_decrease_count_as_of"] = (
        result["work_id"].map(decrease_counts).fillna(0).astype("int64")
    )
    result["max_physical_progress_drop_pct_as_of"] = (
        result["work_id"].map(maximum_drop).fillna(0.0).astype("float64")
    )

    same_day_extra = visible.duplicated(["work_id", "report_date"], keep="first")
    same_day_counts = same_day_extra.groupby(visible["work_id"]).sum()
    result["same_day_progress_extra_count_as_of"] = (
        result["work_id"].map(same_day_counts).fillna(0).astype("int64")
    )

    elapsed_days = (
        result["latest_progress_report_date_as_of"]
        - result["first_progress_report_date_as_of"]
    ).dt.days
    first_physical = result["work_id"].map(grouped["physical_progress_pct"].first())
    physical_change = result["latest_physical_progress_pct_as_of"] - first_physical
    result["physical_progress_velocity_pct_per_30d"] = (
        physical_change / elapsed_days.where(elapsed_days.gt(0)) * 30.0
    )
    return result[PROGRESS_AGGREGATE_COLUMNS]


def asset_records_as_of(assets: pd.DataFrame, as_of_date: date) -> pd.DataFrame:
    """Return conservative asset records with future closure events masked."""

    as_of = pd.Timestamp(as_of_date)
    visible = assets.loc[assets["completion_date"].le(as_of)].copy()
    for field in ASSET_EVENT_DATE_COLUMNS:
        visible[field] = visible[field].where(visible[field].le(as_of))
    visible["final_expenditure_inr"] = visible["final_expenditure_inr"].where(
        visible["completion_marked_date"].notna()
    )
    safe_columns = [
        "work_id",
        "asset_id",
        "asset_type",
        "user_agency",
        *ASSET_EVENT_DATE_COLUMNS,
        "final_expenditure_inr",
    ]
    return visible[safe_columns]


def aggregate_assets_as_of(assets: pd.DataFrame, as_of_date: date) -> pd.DataFrame:
    """Aggregate assets by work even when future inputs become one-to-many."""

    visible = asset_records_as_of(assets, as_of_date)
    if visible.empty:
        return pd.DataFrame(columns=ASSET_AGGREGATE_COLUMNS)

    grouped = visible.groupby("work_id", sort=False)
    result = grouped.agg(
        asset_record_count_as_of=("asset_id", "size"),
        completion_date_as_of=("completion_date", "max"),
        final_expenditure_inr_as_of=("final_expenditure_inr", lambda x: x.sum(min_count=1)),
    ).reset_index()
    result["is_completed_as_of"] = True
    event_flags = {
        "completion_marked_as_of": "completion_marked_date",
        "uc_recorded_as_of": "utilization_certificate_date",
        "handover_recorded_as_of": "handover_date",
        "public_use_recorded_as_of": "public_use_date",
        "audit_recorded_as_of": "audit_date",
    }
    for output, source in event_flags.items():
        event_by_work = visible[source].notna().groupby(visible["work_id"]).any()
        result[output] = result["work_id"].map(event_by_work).fillna(False).astype(bool)
    return result[ASSET_AGGREGATE_COLUMNS]


def safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Divide only by positive denominators and never manufacture zero for N/A."""

    ratio = numerator.astype("float64") / denominator.astype("float64").where(
        denominator.gt(0)
    )
    return ratio.replace([np.inf, -np.inf], np.nan)
