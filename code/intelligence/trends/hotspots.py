"""Current detector-prevalence hotspots for dashboard context only."""

from __future__ import annotations

import pandas as pd

from .monthly import encode_group_value


MINIMUM_HOTSPOT_WORKS = 20
HOTSPOT_GROUP_FIELDS: dict[str, tuple[str, ...]] = {
    "STATE": ("state_name",),
    "DISTRICT": ("state_name", "district"),
    "SECTOR": ("sector",),
    "IMPLEMENTING_AGENCY": ("implementing_agency_id",),
}


def _boolean(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values.dtype):
        return values.fillna(False).astype(bool)
    return values.astype("string").str.casefold().eq("true").fillna(False)


def build_detector_hotspots(
    features: pd.DataFrame,
    anomaly: pd.DataFrame,
    duplicates: pd.DataFrame,
    payment_summary: pd.DataFrame,
    fund_progress: pd.DataFrame,
    compliance_summary: pd.DataFrame,
    predictive_scores: pd.DataFrame,
    entities: pd.DataFrame,
    *,
    minimum_work_count: int = MINIMUM_HOTSPOT_WORKS,
) -> pd.DataFrame:
    """Aggregate transparent detector rates without emitting a composite score."""

    spine = features[
        ["work_id", "state_name", "district", "sector", "implementing_agency_id"]
    ].copy()
    for frame, columns in (
        (anomaly, ["work_id", "within_stage_anomaly_percentile_0_100"]),
        (duplicates, ["work_id", "review_candidate"]),
        (payment_summary, ["work_id", "has_payment_irregularity_evidence"]),
        (
            fund_progress,
            ["work_id", "persistent_large_reported_gap_review_heuristic"],
        ),
        (
            compliance_summary,
            ["work_id", "rules_review_count", "rules_non_compliant_count"],
        ),
        (
            predictive_scores,
            ["work_id", "already_overdue_as_of", "already_over_sanction_as_of"],
        ),
    ):
        spine = spine.merge(frame[columns], on="work_id", how="left", validate="one_to_one")

    spine["_top_anomaly"] = pd.to_numeric(
        spine["within_stage_anomaly_percentile_0_100"], errors="coerce"
    ).ge(90.0)
    spine["_duplicate"] = _boolean(spine["review_candidate"])
    spine["_payment"] = _boolean(spine["has_payment_irregularity_evidence"])
    spine["_persistent_gap"] = _boolean(
        spine["persistent_large_reported_gap_review_heuristic"]
    )
    spine["_overdue"] = _boolean(spine["already_overdue_as_of"])
    spine["_over_sanction"] = _boolean(spine["already_over_sanction_as_of"])
    spine["_compliance_review"] = pd.to_numeric(
        spine["rules_review_count"], errors="coerce"
    ).fillna(0).gt(0)
    spine["_non_compliant"] = pd.to_numeric(
        spine["rules_non_compliant_count"], errors="coerce"
    ).fillna(0).gt(0)

    agency_names = entities.loc[
        entities["entity_type"].eq("IMPLEMENTING_AGENCY")
    ].set_index("entity_id")["entity_name"]
    records: list[dict[str, object]] = []
    signals = {
        "top_10pct_anomaly": "_top_anomaly",
        "duplicate_review": "_duplicate",
        "payment_evidence": "_payment",
        "persistent_fund_gap": "_persistent_gap",
        "observed_overdue": "_overdue",
        "observed_over_sanction": "_over_sanction",
        "compliance_review": "_compliance_review",
        "deterministic_non_compliant": "_non_compliant",
    }
    for group_type, fields in HOTSPOT_GROUP_FIELDS.items():
        for keys, group in spine.dropna(subset=list(fields)).groupby(
            list(fields), sort=True, dropna=False
        ):
            if len(group) < minimum_work_count:
                continue
            key = keys[0] if isinstance(keys, tuple) and len(keys) == 1 else keys
            group_value = encode_group_value(fields, key)
            label = (
                str(agency_names.get(key, key))
                if group_type == "IMPLEMENTING_AGENCY"
                else group_value
            )
            record: dict[str, object] = {
                "group_type": group_type,
                "group_value": group_value,
                "group_label": label,
                "work_count": int(len(group)),
            }
            for prefix, column in signals.items():
                count = int(group[column].sum())
                record[f"{prefix}_work_count"] = count
                if prefix != "deterministic_non_compliant":
                    record[f"{prefix}_share"] = count / len(group)
            records.append(record)
    result = pd.DataFrame.from_records(records)
    return result.sort_values(["group_type", "group_value"], kind="stable").reset_index(drop=True)
