"""Monthly operational-event series with causal historical baselines."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from intelligence.data.loader import OperationalDataBundle

from .robust import (
    EWMA_ALPHA,
    LOOKBACK_MONTHS,
    MINIMUM_HISTORICAL_EVENTS,
    MINIMUM_PRIOR_MONTHS,
    ROBUST_Z_THRESHOLD,
)


LATEST_COMPLETE_MONTH = "2026-08"
TREND_METRICS = (
    "recommendation_work_count",
    "recommended_amount_inr",
    "sanction_work_count",
    "sanctioned_amount_inr",
    "released_payment_count",
    "released_payment_amount_inr",
    "progress_report_count",
)

GROUP_FIELDS: dict[str, tuple[str, ...]] = {
    "STATE": ("state_name",),
    "DISTRICT": ("state_name", "district"),
    "SECTOR": ("sector",),
    "STATE_SECTOR": ("state_name", "sector"),
    "DISTRICT_SECTOR": ("state_name", "district", "sector"),
}

TREND_TIMESERIES_COLUMNS = [
    "group_type",
    "group_value",
    "metric",
    "month",
    "current_value",
    "current_event_count",
    "baseline_month_count",
    "historical_event_support",
    "median",
    "mad",
    "q1",
    "q3",
    "iqr",
    "p10",
    "p90",
    "robust_z",
    "deviation_method",
    "ewma",
    "trend_deviation_flag",
]


def latest_complete_month(as_of_date: date) -> pd.Period:
    return pd.Timestamp(as_of_date).to_period("M") - 1


def encode_group_value(fields: tuple[str, ...], values: object) -> str:
    if len(fields) == 1:
        unpacked = values if isinstance(values, tuple) else (values,)
    elif isinstance(values, tuple):
        unpacked = values
    else:
        unpacked = tuple(values)
    return "|".join(f"{field}={value}" for field, value in zip(fields, unpacked))


def group_value_for_work(work: pd.Series | object, group_type: str) -> str | None:
    fields = GROUP_FIELDS[group_type]
    values: list[object] = []
    for field in fields:
        value = work[field] if isinstance(work, pd.Series) else getattr(work, field)
        if pd.isna(value):
            return None
        values.append(value)
    return encode_group_value(fields, tuple(values) if len(values) > 1 else values[0])


def _event_metric_frames(
    bundle: OperationalDataBundle,
    as_of_date: date,
) -> dict[str, pd.DataFrame]:
    """Return safe event rows; closure/completion dates are intentionally absent."""

    works = bundle.works
    payments = bundle.payments
    progress = bundle.progress
    as_of = pd.Timestamp(as_of_date)

    recommendation = works[["work_id", "recommendation_date", "recommended_amount_inr"]].rename(
        columns={"recommendation_date": "event_date"}
    )
    sanction = works.loc[
        works["sanction_date"].notna(),
        ["work_id", "sanction_date", "sanctioned_amount_inr"],
    ].rename(columns={"sanction_date": "event_date"})
    released = payments.loc[
        payments["payment_status"].eq("Released"),
        ["work_id", "payment_release_date", "payment_amount_inr"],
    ].rename(columns={"payment_release_date": "event_date"})
    reports = progress[["work_id", "report_date"]].rename(columns={"report_date": "event_date"})

    frames = {
        "recommendation_work_count": recommendation.assign(value=1.0),
        "recommended_amount_inr": recommendation.assign(
            value=pd.to_numeric(recommendation["recommended_amount_inr"], errors="coerce")
        ),
        "sanction_work_count": sanction.assign(value=1.0),
        "sanctioned_amount_inr": sanction.assign(
            value=pd.to_numeric(sanction["sanctioned_amount_inr"], errors="coerce")
        ),
        "released_payment_count": released.assign(value=1.0),
        "released_payment_amount_inr": released.assign(
            value=pd.to_numeric(released["payment_amount_inr"], errors="coerce")
        ),
        "progress_report_count": reports.assign(value=1.0),
    }
    complete_month = latest_complete_month(as_of_date)
    safe: dict[str, pd.DataFrame] = {}
    for metric, frame in frames.items():
        current = frame.loc[
            frame["event_date"].notna()
            & frame["event_date"].le(as_of)
            & frame["event_date"].dt.to_period("M").le(complete_month),
            ["work_id", "event_date", "value"],
        ].copy()
        current = current.loc[current["value"].notna()]
        current["month"] = current["event_date"].dt.to_period("M")
        safe[metric] = current
    return safe


def _dense_group_metric(
    events: pd.DataFrame,
    fields: tuple[str, ...],
    group_type: str,
    metric: str,
    complete_month: pd.Period,
) -> pd.DataFrame:
    grouped = (
        events.groupby([*fields, "month"], dropna=False, sort=True)
        .agg(current_value=("value", "sum"), current_event_count=("work_id", "size"))
        .reset_index()
    )
    records: list[pd.DataFrame] = []
    for keys, values in grouped.groupby(list(fields), dropna=False, sort=True):
        key_tuple = keys if isinstance(keys, tuple) else (keys,)
        if any(pd.isna(value) for value in key_tuple):
            continue
        first_month = values["month"].min()
        months = pd.period_range(first_month, complete_month, freq="M")
        indexed = values.set_index("month")[["current_value", "current_event_count"]]
        dense = indexed.reindex(months, fill_value=0.0).rename_axis("month").reset_index()
        dense["current_event_count"] = dense["current_event_count"].astype("int64")
        dense.insert(0, "metric", metric)
        dense.insert(0, "group_value", encode_group_value(fields, keys))
        dense.insert(0, "group_type", group_type)
        records.append(dense)
    if not records:
        return pd.DataFrame(columns=TREND_TIMESERIES_COLUMNS)
    return pd.concat(records, ignore_index=True)


def _add_causal_statistics(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.sort_values("month", kind="stable").reset_index(drop=True).copy()
    values = result["current_value"].astype("float64").to_numpy()
    event_counts = result["current_event_count"].astype("int64").to_numpy()
    result["ewma"] = pd.Series(values).ewm(alpha=EWMA_ALPHA, adjust=False).mean()
    statistical_rows: list[dict[str, object]] = []
    for position, current in enumerate(values):
        start = max(0, position - LOOKBACK_MONTHS)
        history = values[start:position]
        history_support = int(event_counts[start:position].sum())
        enough_months = history.size >= MINIMUM_PRIOR_MONTHS
        enough_support = history_support >= MINIMUM_HISTORICAL_EVENTS
        if history.size:
            median = float(np.median(history))
            mad = float(np.median(np.abs(history - median)))
            q1, q3 = (float(value) for value in np.quantile(history, [0.25, 0.75]))
            iqr = q3 - q1
            p10, p90 = (float(value) for value in np.quantile(history, [0.10, 0.90]))
            if mad > 0:
                candidate_z = 0.6745 * (float(current) - median) / mad
                candidate_method = "MAD"
            elif iqr > 0:
                candidate_z = (float(current) - median) / (iqr / 1.349)
                candidate_method = "IQR_FALLBACK"
            else:
                candidate_z = None
                candidate_method = "CONSTANT_BASELINE_NO_DEVIATION"
        else:
            median = mad = q1 = q3 = iqr = p10 = p90 = float("nan")
            candidate_z = None
            candidate_method = "NO_HISTORY"
        robust_z = candidate_z if enough_months and enough_support else None
        statistical_rows.append(
            {
                "baseline_month_count": int(history.size),
                "historical_event_support": history_support,
                "median": median,
                "mad": mad,
                "q1": q1,
                "q3": q3,
                "iqr": iqr,
                "p10": p10,
                "p90": p90,
                "robust_z": np.nan if robust_z is None else float(robust_z),
                "deviation_method": (
                    candidate_method
                    if enough_months and enough_support
                    else "INSUFFICIENT_PRIOR_MONTHS"
                    if not enough_months
                    else "INSUFFICIENT_HISTORICAL_EVENT_SUPPORT"
                ),
                "trend_deviation_flag": bool(
                    robust_z is not None and abs(float(robust_z)) >= ROBUST_Z_THRESHOLD
                ),
            }
        )
    statistics = pd.DataFrame.from_records(statistical_rows)
    return pd.concat([result, statistics], axis=1)


def build_trend_timeseries(
    bundle: OperationalDataBundle,
    as_of_date: date,
) -> pd.DataFrame:
    """Build long-form monthly operational trends through the latest complete month."""

    metadata = bundle.works[["work_id", "state_name", "district", "sector"]]
    metric_frames = _event_metric_frames(bundle, as_of_date)
    complete_month = latest_complete_month(as_of_date)
    pieces: list[pd.DataFrame] = []
    for metric in TREND_METRICS:
        events = metric_frames[metric].merge(metadata, on="work_id", how="left", validate="many_to_one")
        for group_type, fields in GROUP_FIELDS.items():
            dense = _dense_group_metric(events, fields, group_type, metric, complete_month)
            for _, group in dense.groupby(["group_type", "group_value", "metric"], sort=True):
                pieces.append(_add_causal_statistics(group))
    result = pd.concat(pieces, ignore_index=True)
    result["month"] = result["month"].astype(str)
    result = result[TREND_TIMESERIES_COLUMNS].sort_values(
        ["group_type", "group_value", "metric", "month"], kind="stable"
    ).reset_index(drop=True)
    if result["month"].gt(str(complete_month)).any():
        raise RuntimeError("Incomplete or future month leaked into trend series")
    return result


def build_trend_alerts(timeseries: pd.DataFrame) -> pd.DataFrame:
    alerts = timeseries.loc[timeseries["trend_deviation_flag"].astype(bool)].copy()
    alerts.insert(0, "alert_type", "OPERATIONAL_TREND_DEVIATION")
    alerts["evidence_summary"] = alerts.apply(
        lambda row: (
            f"{row['metric']} for {row['group_value']} in {row['month']} has signed "
            f"robust z {row['robust_z']:.3f} against {int(row['baseline_month_count'])} "
            "causal prior months."
        ),
        axis=1,
    )
    return alerts.sort_values(
        ["month", "group_type", "group_value", "metric"], kind="stable"
    ).reset_index(drop=True)
