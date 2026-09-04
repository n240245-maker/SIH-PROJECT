"""Lifecycle-aware robust peer benchmarking, separate from model scoring."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd


MINIMUM_PEER_GROUP_SIZE = 20
PEER_OUTLIER_ABSOLUTE_DEVIATION = 3.5

PEER_HIERARCHY: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "LEVEL_1_LIFECYCLE_STATE_SECTOR_SUB_SECTOR",
        ("lifecycle_stage", "state_name", "sector", "sub_sector"),
    ),
    (
        "LEVEL_2_LIFECYCLE_STATE_SECTOR",
        ("lifecycle_stage", "state_name", "sector"),
    ),
    (
        "LEVEL_3_LIFECYCLE_SECTOR_SUB_SECTOR",
        ("lifecycle_stage", "sector", "sub_sector"),
    ),
    ("LEVEL_4_LIFECYCLE_SECTOR", ("lifecycle_stage", "sector")),
    ("LEVEL_5_LIFECYCLE", ("lifecycle_stage",)),
)

PRE_SANCTION_PEER_METRICS = (
    "recommended_amount_inr",
    "technical_estimate_amount_inr",
    "estimate_to_recommended_ratio",
)

EXECUTION_PEER_METRICS = (
    "recommended_amount_inr",
    "technical_estimate_amount_inr",
    "sanctioned_amount_inr",
    "estimate_to_recommended_ratio",
    "sanction_to_recommended_ratio",
    "sanction_to_estimate_ratio",
    "released_payment_total_inr_as_of",
    "largest_payment_share_as_of",
    "expenditure_to_sanction_pct_as_of",
    "financial_overrun_pct_as_of",
    "latest_physical_progress_pct_as_of",
    "latest_financial_progress_pct_as_of",
    "financial_minus_physical_gap_pct_as_of",
    "expected_minus_physical_gap_pct_as_of",
    "physical_progress_decrease_count_as_of",
    "max_physical_progress_drop_pct_as_of",
    "physical_progress_velocity_pct_per_30d",
    "days_since_last_payment_as_of",
    "overdue_days_as_of",
    "schedule_elapsed_ratio_as_of",
)

STAGE_PEER_METRICS: Mapping[str, tuple[str, ...]] = {
    "PRE_SANCTION": PRE_SANCTION_PEER_METRICS,
    "EXECUTION": EXECUTION_PEER_METRICS,
    "COMPLETION": EXECUTION_PEER_METRICS,
}

EVIDENCE_COLUMNS = (
    "work_id",
    "lifecycle_stage",
    "metric",
    "observed_value",
    "peer_median",
    "peer_mad",
    "peer_q1",
    "peer_q3",
    "peer_iqr",
    "peer_p10",
    "peer_p90",
    "robust_deviation",
    "absolute_robust_deviation",
    "deviation_method",
    "peer_group_level",
    "peer_group_size",
    "statistical_peer_outlier",
    "direction",
)


def robust_deviation(
    observed_value: float | int | None,
    peer_median: float | int | None,
    peer_mad: float | int | None,
    peer_iqr: float | int | None,
) -> tuple[float | None, str]:
    """Return a finite signed robust deviation and the method used."""

    values = (observed_value, peer_median, peer_mad, peer_iqr)
    if observed_value is None or peer_median is None:
        return None, "OBSERVED_OR_PEER_VALUE_MISSING"
    if any(pd.isna(value) for value in values[:2]):
        return None, "OBSERVED_OR_PEER_VALUE_MISSING"

    observed = float(observed_value)
    median = float(peer_median)
    mad = float(peer_mad) if peer_mad is not None and pd.notna(peer_mad) else 0.0
    iqr = float(peer_iqr) if peer_iqr is not None and pd.notna(peer_iqr) else 0.0
    if mad > 0:
        return float(0.6745 * (observed - median) / mad), "MODIFIED_Z_MAD"
    if iqr > 0:
        return float((observed - median) / (iqr / 1.349)), "STANDARDIZED_IQR_FALLBACK"
    return None, "UNAVAILABLE_CONSTANT_PEER_DISTRIBUTION"


def _peer_stats(stage_rows: pd.DataFrame, metric: str, keys: Sequence[str]) -> pd.DataFrame:
    grouped = stage_rows.groupby(list(keys), dropna=False, sort=False)[metric]
    stats = grouped.agg(
        peer_group_size="count",
        peer_median="median",
        peer_q1=lambda values: values.quantile(0.25),
        peer_q3=lambda values: values.quantile(0.75),
        peer_p10=lambda values: values.quantile(0.10),
        peer_p90=lambda values: values.quantile(0.90),
        peer_mad=lambda values: (
            (values.dropna() - values.dropna().median()).abs().median()
            if values.notna().any()
            else np.nan
        ),
    ).reset_index()
    stats["peer_iqr"] = stats["peer_q3"] - stats["peer_q1"]
    return stats


def _benchmark_metric(stage_rows: pd.DataFrame, metric: str) -> pd.DataFrame:
    selected = pd.DataFrame(index=stage_rows.index)
    stat_columns = [
        "peer_group_size",
        "peer_median",
        "peer_q1",
        "peer_q3",
        "peer_p10",
        "peer_p90",
        "peer_mad",
        "peer_iqr",
    ]
    for column in stat_columns:
        selected[column] = np.nan
    selected["peer_group_level"] = pd.NA

    unresolved = pd.Series(True, index=stage_rows.index)
    for level_name, keys in PEER_HIERARCHY:
        stats = _peer_stats(stage_rows, metric, keys)
        joined = stage_rows.loc[:, list(keys)].merge(
            stats,
            on=list(keys),
            how="left",
            sort=False,
        )
        joined.index = stage_rows.index
        usable = unresolved & joined["peer_group_size"].ge(MINIMUM_PEER_GROUP_SIZE)
        if usable.any():
            selected.loc[usable, stat_columns] = joined.loc[usable, stat_columns].to_numpy()
            selected.loc[usable, "peer_group_level"] = level_name
            unresolved.loc[usable] = False
        if not unresolved.any():
            break

    if unresolved.any():
        raise ValueError(
            f"No peer cohort with at least {MINIMUM_PEER_GROUP_SIZE} non-null "
            f"observations for {metric} in {stage_rows['lifecycle_stage'].iloc[0]}"
        )

    records: list[dict[str, Any]] = []
    for index, row in stage_rows.iterrows():
        stats = selected.loc[index]
        deviation, method = robust_deviation(
            row[metric], stats["peer_median"], stats["peer_mad"], stats["peer_iqr"]
        )
        absolute = abs(deviation) if deviation is not None else None
        is_outlier = bool(
            absolute is not None and absolute >= PEER_OUTLIER_ABSOLUTE_DEVIATION
        )
        direction = (
            "ABOVE_PEERS"
            if deviation is not None and deviation > 0
            else "BELOW_PEERS"
            if deviation is not None and deviation < 0
            else None
        )
        records.append(
            {
                "work_id": row["work_id"],
                "lifecycle_stage": row["lifecycle_stage"],
                "metric": metric,
                "observed_value": row[metric],
                "peer_median": stats["peer_median"],
                "peer_mad": stats["peer_mad"],
                "peer_q1": stats["peer_q1"],
                "peer_q3": stats["peer_q3"],
                "peer_iqr": stats["peer_iqr"],
                "peer_p10": stats["peer_p10"],
                "peer_p90": stats["peer_p90"],
                "robust_deviation": deviation,
                "absolute_robust_deviation": absolute,
                "deviation_method": method,
                "peer_group_level": stats["peer_group_level"],
                "peer_group_size": int(stats["peer_group_size"]),
                "statistical_peer_outlier": is_outlier,
                "direction": direction,
            }
        )
    return pd.DataFrame.from_records(records, columns=EVIDENCE_COLUMNS)


def build_peer_benchmarks(
    features: pd.DataFrame,
    feature_sets: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, list[str]]]:
    """Create long-form peer evidence and a one-row-per-work summary."""

    evidence_frames: list[pd.DataFrame] = []
    metrics_used: dict[str, list[str]] = {}
    for stage, candidates in STAGE_PEER_METRICS.items():
        selected_features = set(
            feature_sets["stages"][stage]["selected_features"]
        )
        metrics = [metric for metric in candidates if metric in selected_features]
        if not metrics:
            raise ValueError(f"No peer benchmark metrics available for {stage}")
        metrics_used[stage] = metrics
        stage_rows = features.loc[features["lifecycle_stage"].eq(stage)].copy()
        for metric in metrics:
            evidence_frames.append(_benchmark_metric(stage_rows, metric))

    # Drop frame-local all-null columns before concatenation to avoid pandas'
    # deprecated all-NA dtype inference, then restore the governed schema.
    evidence = pd.concat(
        [frame.dropna(axis="columns", how="all") for frame in evidence_frames],
        ignore_index=True,
    ).reindex(columns=EVIDENCE_COLUMNS)
    base = features.loc[:, ["work_id", "lifecycle_stage"]].copy()
    summary_records: list[dict[str, Any]] = []
    for work_id, group in evidence.groupby("work_id", sort=False):
        usable = group.loc[
            group["observed_value"].notna() & group["peer_group_level"].notna()
        ]
        deviations = usable.dropna(subset=["robust_deviation"])
        top_metric: str | None = None
        top_value: float | None = None
        max_absolute: float | None = None
        if not deviations.empty:
            top_index = deviations["absolute_robust_deviation"].idxmax()
            top = deviations.loc[top_index]
            top_metric = str(top["metric"])
            top_value = float(top["robust_deviation"])
            max_absolute = float(top["absolute_robust_deviation"])
        summary_records.append(
            {
                "work_id": work_id,
                "peer_metric_count": int(len(usable)),
                "peer_outlier_count": int(usable["statistical_peer_outlier"].sum()),
                "max_abs_peer_deviation": max_absolute,
                "top_peer_deviation_metric": top_metric,
                "top_peer_deviation_value": top_value,
            }
        )

    summary = base.merge(
        pd.DataFrame.from_records(summary_records),
        on="work_id",
        how="left",
        validate="one_to_one",
    )
    return evidence, summary, metrics_used
