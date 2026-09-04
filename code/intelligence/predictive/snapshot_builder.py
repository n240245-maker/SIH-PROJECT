"""Construct leakage-safe point-in-time landmark rows from operational histories."""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from intelligence.data.loader import OperationalDataBundle
from intelligence.features.aggregations import (
    natural_payment_stage,
)

from .feature_sets import POINT_IN_TIME_PREDICTORS
from .targets import COST_OVERRUN_TARGET, DELAY_TARGET, build_completed_work_outcomes


LANDMARK_FRACTIONS = (0.25, 0.50, 0.75)

PAYMENT_DEFAULTS: dict[str, Any] = {
    "released_payment_count_as_of": 0,
    "released_payment_total_inr_as_of": 0,
    "largest_payment_inr_as_of": np.nan,
    "mean_payment_inr_as_of": np.nan,
    "largest_payment_share_as_of": np.nan,
    "days_since_last_payment_as_of": np.nan,
}
PROGRESS_DEFAULTS: dict[str, Any] = {
    "progress_report_count_as_of": 0,
    "latest_physical_progress_pct_as_of": np.nan,
    "latest_financial_progress_pct_as_of": np.nan,
    "latest_expected_progress_pct_as_of": np.nan,
    "financial_minus_physical_gap_pct_as_of": np.nan,
    "expected_minus_physical_gap_pct_as_of": np.nan,
    "physical_progress_decrease_count_as_of": 0,
    "max_physical_progress_drop_pct_as_of": 0.0,
    "physical_progress_velocity_pct_per_30d": np.nan,
}


def derive_landmark_date(work: pd.Series, fraction: float) -> pd.Timestamp:
    """Return the exact fractional point in the work's planned interval."""

    start = pd.Timestamp(work["expected_start_date"])
    end = pd.Timestamp(work["expected_completion_date"])
    return start + (end - start) * fraction


def _scalar_ratio(numerator: Any, denominator: Any) -> float:
    if pd.isna(numerator) or pd.isna(denominator) or float(denominator) <= 0:
        return float("nan")
    return float(numerator) / float(denominator)


def _payment_features(payments: pd.DataFrame, landmark_date: pd.Timestamp) -> dict[str, Any]:
    visible = payments.loc[
        payments["payment_status"].eq("Released")
        & payments["payment_release_date"].le(landmark_date)
    ].copy()
    if visible.empty:
        return dict(PAYMENT_DEFAULTS)
    visible["_stage"] = natural_payment_stage(visible["payment_stage"])
    visible = visible.sort_values(
        ["payment_release_date", "_stage", "payment_id"],
        kind="stable",
        na_position="last",
    )
    amounts = visible["payment_amount_inr"].astype("float64")
    total = float(amounts.sum())
    largest = float(amounts.max())
    return {
        "released_payment_count_as_of": int(len(visible)),
        "released_payment_total_inr_as_of": total,
        "largest_payment_inr_as_of": largest,
        "mean_payment_inr_as_of": float(amounts.mean()),
        "largest_payment_share_as_of": largest / total if total > 0 else np.nan,
        "days_since_last_payment_as_of": int(
            (landmark_date - visible.iloc[-1]["payment_release_date"]).days
        ),
    }


def _progress_features(progress: pd.DataFrame, landmark_date: pd.Timestamp) -> dict[str, Any]:
    visible = progress.loc[progress["report_date"].le(landmark_date)].sort_values(
        ["report_date", "progress_id"], kind="stable"
    )
    if visible.empty:
        return dict(PROGRESS_DEFAULTS)
    latest = visible.iloc[-1]
    physical = visible["physical_progress_pct"].astype("float64")
    changes = physical.diff()
    drops = -changes.loc[changes.lt(0)]
    first_date = visible.iloc[0]["report_date"]
    last_date = latest["report_date"]
    elapsed_days = int((last_date - first_date).days)
    velocity = (
        float((physical.iloc[-1] - physical.iloc[0]) / elapsed_days * 30.0)
        if elapsed_days > 0
        else np.nan
    )
    return {
        "progress_report_count_as_of": int(len(visible)),
        "latest_physical_progress_pct_as_of": float(latest["physical_progress_pct"]),
        "latest_financial_progress_pct_as_of": float(latest["financial_progress_pct"]),
        "latest_expected_progress_pct_as_of": float(
            latest["expected_progress_pct_by_date"]
        ),
        "financial_minus_physical_gap_pct_as_of": float(
            latest["financial_progress_pct"] - latest["physical_progress_pct"]
        ),
        "expected_minus_physical_gap_pct_as_of": float(
            latest["expected_progress_pct_by_date"] - latest["physical_progress_pct"]
        ),
        "physical_progress_decrease_count_as_of": int(changes.lt(0).sum()),
        "max_physical_progress_drop_pct_as_of": (
            float(drops.max()) if not drops.empty else 0.0
        ),
        "physical_progress_velocity_pct_per_30d": velocity,
    }


def _point_in_time_features(
    work: pd.Series,
    payments: pd.DataFrame,
    progress: pd.DataFrame,
    landmark_date: pd.Timestamp,
    landmark_fraction: float,
) -> dict[str, Any]:
    payment_values = _payment_features(payments, landmark_date)
    progress_values = _progress_features(progress, landmark_date)

    recommended = work["recommended_amount_inr"]
    estimate = work["technical_estimate_amount_inr"]
    sanction = work["sanctioned_amount_inr"]
    released_total = payment_values["released_payment_total_inr_as_of"]
    planned_duration = (
        work["expected_completion_date"] - work["expected_start_date"]
    ).days
    visible_actual_start = (
        work["actual_start_date"]
        if pd.notna(work["actual_start_date"])
        and work["actual_start_date"] <= landmark_date
        else pd.NaT
    )
    overrun_amount = (
        max(float(released_total) - float(sanction), 0.0)
        if pd.notna(sanction) and float(sanction) > 0
        else float("nan")
    )
    elapsed_from_plan = max(
        0,
        int((landmark_date - work["expected_start_date"]).days),
    )

    values: dict[str, Any] = {
        "recommended_amount_inr": recommended,
        "technical_estimate_amount_inr": estimate,
        "sanctioned_amount_inr": sanction,
        "estimate_to_recommended_ratio": _scalar_ratio(estimate, recommended),
        "sanction_to_recommended_ratio": _scalar_ratio(sanction, recommended),
        "sanction_to_estimate_ratio": _scalar_ratio(sanction, estimate),
        "days_recommendation_to_sanction": int(
            (work["sanction_date"] - work["recommendation_date"]).days
        ),
        "planned_duration_days": planned_duration,
        "days_sanction_to_expected_start": int(
            (work["expected_start_date"] - work["sanction_date"]).days
        ),
        **payment_values,
        "expenditure_to_sanction_pct_as_of": (
            _scalar_ratio(released_total, sanction) * 100.0
        ),
        "financial_overrun_amount_inr_as_of": overrun_amount,
        "financial_overrun_pct_as_of": _scalar_ratio(overrun_amount, sanction) * 100.0,
        **progress_values,
        "actual_start_available_as_of": bool(pd.notna(visible_actual_start)),
        "days_since_actual_start_as_of": (
            int((landmark_date - visible_actual_start).days)
            if pd.notna(visible_actual_start)
            else np.nan
        ),
        "days_to_expected_completion_as_of": int(
            (work["expected_completion_date"] - landmark_date).days
        ),
        "schedule_elapsed_ratio_as_of": _scalar_ratio(
            elapsed_from_plan, planned_duration
        ),
        "landmark_fraction": float(landmark_fraction),
    }
    return {column: values[column] for column in POINT_IN_TIME_PREDICTORS}


def build_historical_landmark_snapshots(
    bundle: OperationalDataBundle,
    as_of_date: date,
) -> pd.DataFrame:
    """Create one eligible 25/50/75% historical row per completed work/landmark."""

    outcomes = build_completed_work_outcomes(bundle, as_of_date).set_index("work_id")
    works = bundle.works.set_index("work_id", drop=False)
    payment_groups = {
        str(work_id): group.copy()
        for work_id, group in bundle.payments.groupby("work_id", sort=False)
    }
    progress_groups = {
        str(work_id): group.copy()
        for work_id, group in bundle.progress.groupby("work_id", sort=False)
    }
    empty_payments = bundle.payments.iloc[0:0].copy()
    empty_progress = bundle.progress.iloc[0:0].copy()

    rows: list[dict[str, Any]] = []
    for work_id, outcome in outcomes.iterrows():
        work = works.loc[work_id]
        start = work["expected_start_date"]
        end = work["expected_completion_date"]
        if pd.isna(start) or pd.isna(end) or end <= start:
            continue
        for fraction in LANDMARK_FRACTIONS:
            landmark = derive_landmark_date(work, fraction)
            if (
                pd.isna(work["sanction_date"])
                or work["sanction_date"] > landmark
                or outcome["completion_date"] <= landmark
            ):
                continue
            work_key = str(work_id)
            record: dict[str, Any] = {
                "work_id": work_key,
                "landmark_fraction": float(fraction),
                "landmark_date": landmark,
                "outcome_known_at_landmark": False,
                DELAY_TARGET: outcome[DELAY_TARGET],
                COST_OVERRUN_TARGET: outcome[COST_OVERRUN_TARGET],
            }
            record.update(
                _point_in_time_features(
                    work,
                    payment_groups.get(work_key, empty_payments),
                    progress_groups.get(work_key, empty_progress),
                    landmark,
                    fraction,
                )
            )
            rows.append(record)

    ordered = [
        "work_id",
        "landmark_fraction",
        "landmark_date",
        "outcome_known_at_landmark",
        DELAY_TARGET,
        COST_OVERRUN_TARGET,
        *[name for name in POINT_IN_TIME_PREDICTORS if name != "landmark_fraction"],
    ]
    snapshots = pd.DataFrame(rows, columns=ordered)
    if not snapshots.empty:
        snapshots[DELAY_TARGET] = snapshots[DELAY_TARGET].astype("Int64")
        snapshots[COST_OVERRUN_TARGET] = snapshots[COST_OVERRUN_TARGET].astype("Int64")
    validate_historical_snapshots(snapshots)
    return snapshots


def validate_historical_snapshots(snapshots: pd.DataFrame) -> None:
    if snapshots.duplicated(["work_id", "landmark_fraction"]).any():
        raise ValueError("Historical snapshots contain duplicate work/landmark rows")
    if snapshots["outcome_known_at_landmark"].any():
        raise ValueError("A historical snapshot was included after its outcome")
    predictor_columns = [
        column for column in snapshots.columns if column in POINT_IN_TIME_PREDICTORS
    ]
    if set(predictor_columns) != set(POINT_IN_TIME_PREDICTORS):
        raise ValueError("Historical predictor columns do not match the allowlist")
    prohibited_fragments = (
        "source_current_",
        "actual_duration",
        "completion_delay",
        "final_expenditure",
    )
    prohibited = [
        column
        for column in predictor_columns
        if any(fragment in column for fragment in prohibited_fragments)
    ]
    if prohibited:
        raise ValueError(f"Historical predictors contain outcome leakage: {prohibited}")
