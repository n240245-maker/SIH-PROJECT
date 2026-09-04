"""As-of fund-versus-physical-progress evidence with persistence context."""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from intelligence.features.aggregations import progress_reports_as_of


LARGE_POSITIVE_GAP_HEURISTIC_PCT = 25.0
PERSISTENT_REPORT_COUNT_HEURISTIC = 2


def gap_persistence_statistics(
    gaps: pd.Series,
    *,
    large_gap_threshold: float = LARGE_POSITIVE_GAP_HEURISTIC_PCT,
) -> dict[str, Any]:
    """Summarize positive and consecutive large reported gaps in stable order."""

    numeric = pd.to_numeric(gaps, errors="coerce").dropna().astype("float64")
    if numeric.empty:
        return {
            "latest_gap": None,
            "maximum_gap": None,
            "mean_gap": None,
            "positive_gap_report_count": 0,
            "large_gap_report_count": 0,
            "latest_consecutive_large_gap_count": 0,
            "maximum_consecutive_large_gap_count": 0,
        }
    large = numeric.ge(large_gap_threshold)
    current_run = 0
    maximum_run = 0
    for is_large in large:
        current_run = current_run + 1 if bool(is_large) else 0
        maximum_run = max(maximum_run, current_run)
    return {
        "latest_gap": float(numeric.iloc[-1]),
        "maximum_gap": float(numeric.max()),
        "mean_gap": float(numeric.mean()),
        "positive_gap_report_count": int(numeric.gt(0).sum()),
        "large_gap_report_count": int(large.sum()),
        "latest_consecutive_large_gap_count": int(current_run),
        "maximum_consecutive_large_gap_count": int(maximum_run),
    }


def build_fund_progress_evidence(
    project_features: pd.DataFrame,
    progress: pd.DataFrame,
    as_of_date: date,
) -> pd.DataFrame:
    """Build one evidence row per work with a positive visible sanction."""

    required = {
        "work_id",
        "lifecycle_stage",
        "source_current_status",
        "sanctioned_amount_inr",
        "released_payment_count_as_of",
        "released_payment_total_inr_as_of",
        "latest_physical_progress_pct_as_of",
        "latest_financial_progress_pct_as_of",
        "progress_report_count_as_of",
    }
    missing = sorted(required.difference(project_features.columns))
    if missing:
        raise ValueError(f"Fund-progress feature inputs missing: {missing}")

    visible_progress = progress_reports_as_of(progress, as_of_date).copy()
    visible_progress["_reported_financial_minus_physical_gap"] = (
        visible_progress["financial_progress_pct"].astype("float64")
        - visible_progress["physical_progress_pct"].astype("float64")
    )
    histories = {
        str(work_id): gap_persistence_statistics(
            group["_reported_financial_minus_physical_gap"]
        )
        for work_id, group in visible_progress.groupby("work_id", sort=False)
    }

    sanctioned = pd.to_numeric(
        project_features["sanctioned_amount_inr"], errors="coerce"
    )
    applicable = project_features.loc[sanctioned.gt(0)].copy()
    applicable["sanctioned_amount_inr"] = sanctioned.loc[applicable.index]
    released_total = pd.to_numeric(
        applicable["released_payment_total_inr_as_of"], errors="coerce"
    ).fillna(0.0)
    payment_financial = (
        100.0 * released_total / applicable["sanctioned_amount_inr"].astype("float64")
    )
    physical = pd.to_numeric(
        applicable["latest_physical_progress_pct_as_of"], errors="coerce"
    )
    reported_financial = pd.to_numeric(
        applicable["latest_financial_progress_pct_as_of"], errors="coerce"
    )
    fund_gap = payment_financial - physical
    reported_gap = reported_financial - physical
    reconciliation = reported_financial - payment_financial

    output = applicable.loc[:, ["work_id", "lifecycle_stage"]].copy()
    output["payment_based_financial_progress_pct_as_of"] = payment_financial
    output["latest_reported_financial_progress_pct_as_of"] = reported_financial
    output["latest_physical_progress_pct_as_of"] = physical
    output["fund_minus_physical_gap_pct_as_of"] = fund_gap
    output["absolute_fund_minus_physical_gap_pct_as_of"] = fund_gap.abs()
    output["reported_financial_minus_physical_gap_pct_as_of"] = reported_gap
    output["reported_vs_payment_financial_progress_difference_pct"] = reconciliation

    history_fields = (
        "latest_gap",
        "maximum_gap",
        "mean_gap",
        "positive_gap_report_count",
        "large_gap_report_count",
        "latest_consecutive_large_gap_count",
        "maximum_consecutive_large_gap_count",
    )
    for field in history_fields:
        output[field] = output["work_id"].map(
            lambda work_id, name=field: histories.get(str(work_id), {}).get(name)
        )
    count_fields = (
        "positive_gap_report_count",
        "large_gap_report_count",
        "latest_consecutive_large_gap_count",
        "maximum_consecutive_large_gap_count",
    )
    for field in count_fields:
        output[field] = output[field].fillna(0).astype("int64")

    output = output.rename(
        columns={
            "maximum_gap": "max_historical_financial_minus_physical_gap_pct",
            "mean_gap": "mean_historical_financial_minus_physical_gap_pct",
            "latest_gap": "latest_historical_financial_minus_physical_gap_pct",
            "maximum_consecutive_large_gap_count": "max_consecutive_large_gap_reports",
            "latest_consecutive_large_gap_count": "latest_consecutive_large_gap_reports",
        }
    )
    output["progress_report_count_as_of"] = pd.to_numeric(
        applicable["progress_report_count_as_of"], errors="coerce"
    ).fillna(0).astype("int64")
    output["large_positive_gap_heuristic_pct"] = LARGE_POSITIVE_GAP_HEURISTIC_PCT
    output["current_large_positive_fund_gap_review_heuristic"] = fund_gap.ge(
        LARGE_POSITIVE_GAP_HEURISTIC_PCT
    ).fillna(False)
    output["persistent_large_reported_gap_review_heuristic"] = output[
        "max_consecutive_large_gap_reports"
    ].ge(PERSISTENT_REPORT_COUNT_HEURISTIC)

    not_started = applicable["source_current_status"].eq("Sanctioned - Not Started")
    output["status_not_started_with_payment_evidence"] = (
        not_started
        & pd.to_numeric(
            applicable["released_payment_count_as_of"], errors="coerce"
        ).fillna(0).gt(0)
    )
    output["status_not_started_with_physical_progress"] = (
        not_started & physical.fillna(0).gt(0)
    )
    output["evidence_interpretation"] = (
        "Signed reconciliation and persistence evidence for review; heuristic "
        "bands are engineering choices, not MPLADS rules or final decisions."
    )
    return output.reset_index(drop=True)
