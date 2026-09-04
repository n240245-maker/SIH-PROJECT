"""Map independently derived operational trend context to every work."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .monthly import group_value_for_work


WORK_TREND_HIERARCHY = (
    "DISTRICT_SECTOR",
    "DISTRICT",
    "STATE_SECTOR",
    "STATE",
    "SECTOR",
)

WORK_TREND_CONTEXT_COLUMNS = [
    "work_id",
    "selected_trend_group",
    "selected_trend_group_value",
    "strongest_operational_trend_metric",
    "strongest_operational_trend_robust_z",
    "operational_trend_deviation_flag",
    "operational_trend_context_score_0_100",
]


def _inclusive_percentile(values: pd.Series) -> pd.Series:
    result = pd.Series(np.nan, index=values.index, dtype="float64")
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return result
    result.loc[clean.index] = clean.rank(method="average", pct=True) * 100.0
    return result


def build_work_trend_context(
    features: pd.DataFrame,
    timeseries: pd.DataFrame,
    latest_month: str,
) -> pd.DataFrame:
    """Choose the most-specific supported group without detector-hotspot feedback."""

    required = {"work_id", "state_name", "district", "sector"}
    missing = required.difference(features.columns)
    if missing:
        raise ValueError(f"Feature table lacks trend-context fields: {sorted(missing)}")

    latest = timeseries.loc[
        timeseries["month"].eq(latest_month) & timeseries["robust_z"].notna()
    ].copy()
    latest["_abs_robust_z"] = latest["robust_z"].abs()
    deviations = latest["trend_deviation_flag"].astype(bool)
    latest["_deviation_strength"] = np.nan
    latest.loc[deviations, "_deviation_strength"] = _inclusive_percentile(
        latest.loc[deviations, "_abs_robust_z"]
    )
    strongest = (
        latest.sort_values(
            ["group_type", "group_value", "_abs_robust_z", "metric"],
            ascending=[True, True, False, True],
            kind="stable",
        )
        .drop_duplicates(["group_type", "group_value"], keep="first")
        .set_index(["group_type", "group_value"])
    )

    records: list[dict[str, object]] = []
    for work in features[["work_id", "state_name", "district", "sector"]].itertuples(index=False):
        selected: pd.Series | None = None
        selected_type = "NO_SUPPORTED_GROUP"
        selected_value: str | None = None
        for group_type in WORK_TREND_HIERARCHY:
            group_value = group_value_for_work(work, group_type)
            if group_value is not None and (group_type, group_value) in strongest.index:
                selected = strongest.loc[(group_type, group_value)]
                selected_type = group_type
                selected_value = group_value
                break
        if selected is None:
            records.append(
                {
                    "work_id": work.work_id,
                    "selected_trend_group": selected_type,
                    "selected_trend_group_value": selected_value,
                    "strongest_operational_trend_metric": None,
                    "strongest_operational_trend_robust_z": np.nan,
                    "operational_trend_deviation_flag": False,
                    "operational_trend_context_score_0_100": 0.0,
                }
            )
            continue
        flagged = bool(selected["trend_deviation_flag"])
        score = float(selected["_deviation_strength"]) if flagged else 0.0
        records.append(
            {
                "work_id": work.work_id,
                "selected_trend_group": selected_type,
                "selected_trend_group_value": selected_value,
                "strongest_operational_trend_metric": selected["metric"],
                "strongest_operational_trend_robust_z": float(selected["robust_z"]),
                "operational_trend_deviation_flag": flagged,
                "operational_trend_context_score_0_100": score,
            }
        )
    result = pd.DataFrame.from_records(records, columns=WORK_TREND_CONTEXT_COLUMNS)
    if len(result) != 3_000 or not result["work_id"].is_unique:
        raise RuntimeError("Work trend context must contain 3,000 unique work IDs")
    if not result["operational_trend_context_score_0_100"].between(0, 100).all():
        raise RuntimeError("Operational trend context score escaped 0-100")
    return result
